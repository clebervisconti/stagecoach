"""Ingest stage: validation, transcoding, modality detection.

Per SPEC §6.2 and issue #17:
- ffprobe validation with size/duration limits
- Three transcodes: audio16k.wav, analysis.mp4 (≤720p, 15fps), playback.mp4 (+faststart)
- Sprite thumbnails every 5s
- Audio-only and screen-recording detection
- Loudness normalization only on ASR copy
- Sandboxed execution (no network, read-only FS except temp, CPU/mem limits)
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Limits per SPEC §6.2 (heuristic)
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", str(120 * 60)))  # OD-6: 120 minutes
SPRITE_INTERVAL_SECONDS = 5

# Historical flat timeout. Long recordings on one core outgrew it: a 36-minute
# 1080p playback encode was already ~185s at preset medium, so a 120-minute
# file needs a timeout that follows the duration. The cap stays well under a
# day so a stuck ffmpeg is still killed.
_TRANSCODE_TIMEOUT_FLOOR_S = 180
_TRANSCODE_TIMEOUT_CAP_S = 7200
_TRANSCODE_TIMEOUT_FACTOR = {
    "audio": 0.35,
    "analysis": 0.45,
    "playback": 0.6,
    "sprites": 0.25,
}

ProgressFn = Callable[[str, float, Optional[str], Optional[int]], None]
MediaFn = Callable[["MediaInfo"], None]


def transcode_timeout_s(duration_s: float, *, kind: str = "playback") -> int:
    """Seconds to allow one ffmpeg, growing with the recording and bounded."""
    try:
        duration = float(duration_s)
    except (TypeError, ValueError):
        duration = 0.0
    if duration < 0:
        duration = 0.0
    factor = _TRANSCODE_TIMEOUT_FACTOR.get(kind, 0.6)
    scaled = int(duration * factor) + _TRANSCODE_TIMEOUT_FLOOR_S
    return max(_TRANSCODE_TIMEOUT_FLOOR_S, min(scaled, _TRANSCODE_TIMEOUT_CAP_S))


def prepare_eta_s(duration_s: float, pct: float) -> int:
    """Rough remaining prepare time. veryfast playback is the long pole.

    A 36-minute 1080p file was about seven minutes at preset medium. veryfast
    at the same CRF is closer to 0.12× realtime plus a short fixed cost.
    """
    try:
        duration = max(0.0, float(duration_s))
    except (TypeError, ValueError):
        duration = 0.0
    total = max(20.0, duration * 0.12 + 20.0)
    remaining = total * (1.0 - min(max(float(pct), 0.0), 99.0) / 100.0)
    return max(1, int(remaining))

# Supported containers and codecs
SUPPORTED_VIDEO_CONTAINERS = {"mov", "mp4", "webm", "mkv", "avi"}
SUPPORTED_AUDIO_CONTAINERS = {"mp3", "m4a", "wav", "ogg", "flac"}
SUPPORTED_VIDEO_CODECS = {"h264", "hevc", "vp8", "vp9", "av1"}
SUPPORTED_AUDIO_CODECS = {"aac", "mp3", "opus", "vorbis", "flac", "pcm_s16le"}


@dataclass
class MediaInfo:
    """Validated media metadata from ffprobe."""
    
    container: str
    duration: float
    file_size: int
    has_video: bool
    has_audio: bool
    video_codec: Optional[str]
    audio_codec: Optional[str]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    audio_sample_rate: Optional[int]
    audio_channels: Optional[int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "container": self.container,
            "duration": self.duration,
            "file_size": self.file_size,
            "has_video": self.has_video,
            "has_audio": self.has_audio,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
        }


@dataclass
class ModalityFlags:
    """Modality detection results."""
    
    is_audio_only: bool
    is_screen_recording: bool
    person_detection_confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_audio_only": self.is_audio_only,
            "is_screen_recording": self.is_screen_recording,
            "person_detection_confidence": self.person_detection_confidence,
        }


@dataclass
class IngestOutput:
    """Ingest stage outputs."""
    
    media_info: MediaInfo
    modality: ModalityFlags
    artifacts: Dict[str, Path]
    sha256: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "media_info": self.media_info.to_dict(),
            "modality": self.modality.to_dict(),
            "artifacts": {k: str(v) for k, v in self.artifacts.items()},
            "sha256": self.sha256,
        }


def run_ffprobe(input_path: Path) -> Dict[str, Any]:
    """Run ffprobe and return parsed JSON output.
    
    Args:
        input_path: Path to input media file
        
    Returns:
        Parsed ffprobe output
        
    Raises:
        subprocess.CalledProcessError: If ffprobe fails
        ValueError: If output is not valid JSON
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    
    return json.loads(result.stdout)


def validate_media(input_path: Path) -> MediaInfo:
    """Validate media file with ffprobe.
    
    Per SPEC §6.2: Check container, codecs, size, duration limits.
    
    Args:
        input_path: Path to input media file
        
    Returns:
        Validated MediaInfo
        
    Raises:
        ValueError: If file is invalid or exceeds limits
    """
    if not input_path.exists():
        raise ValueError(f"File not found: {input_path}")
    
    file_size = input_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        max_gb = MAX_FILE_SIZE_BYTES / (1024 ** 3)
        actual_gb = file_size / (1024 ** 3)
        raise ValueError(
            f"File size {actual_gb:.2f} GB exceeds limit of {max_gb:.2f} GB"
        )
    
    try:
        probe = run_ffprobe(input_path)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Invalid or corrupt media file: {e.stderr}")
    except json.JSONDecodeError as e:
        raise ValueError(f"ffprobe returned invalid JSON: {e}")
    
    if "format" not in probe:
        raise ValueError("ffprobe output missing format information")
    
    fmt = probe["format"]
    duration = float(fmt.get("duration", 0))
    
    if duration > MAX_DURATION_SECONDS:
        max_min = MAX_DURATION_SECONDS / 60
        actual_min = duration / 60
        raise ValueError(
            f"Duration {actual_min:.1f} minutes exceeds limit of {max_min:.0f} minutes"
        )
    
    # Extract container format
    container = fmt.get("format_name", "").split(",")[0]
    
    # Find video and audio streams
    video_stream = None
    audio_stream = None
    
    for stream in probe.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        elif codec_type == "audio" and audio_stream is None:
            audio_stream = stream
    
    has_video = video_stream is not None
    has_audio = audio_stream is not None
    
    if not has_video and not has_audio:
        raise ValueError("File contains neither video nor audio streams")
    
    # Validate video stream
    video_codec = None
    width = None
    height = None
    fps = None
    
    if has_video:
        video_codec = video_stream.get("codec_name")
        if video_codec not in SUPPORTED_VIDEO_CODECS:
            raise ValueError(
                f"Unsupported video codec: {video_codec}. "
                f"Supported: {', '.join(sorted(SUPPORTED_VIDEO_CODECS))}"
            )
        
        width = video_stream.get("width")
        height = video_stream.get("height")
        
        # Parse fps from r_frame_rate (e.g., "30/1" or "30000/1001")
        r_frame_rate = video_stream.get("r_frame_rate", "0/1")
        if "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            if int(den) != 0:
                fps = int(num) / int(den)
    
    # Validate audio stream
    audio_codec = None
    audio_sample_rate = None
    audio_channels = None
    
    if has_audio:
        audio_codec = audio_stream.get("codec_name")
        if audio_codec not in SUPPORTED_AUDIO_CODECS:
            raise ValueError(
                f"Unsupported audio codec: {audio_codec}. "
                f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_CODECS))}"
            )
        
        audio_sample_rate = audio_stream.get("sample_rate")
        if audio_sample_rate:
            audio_sample_rate = int(audio_sample_rate)
        
        audio_channels = audio_stream.get("channels")
        if audio_channels:
            audio_channels = int(audio_channels)
    
    return MediaInfo(
        container=container,
        duration=duration,
        file_size=file_size,
        has_video=has_video,
        has_audio=has_audio,
        video_codec=video_codec,
        audio_codec=audio_codec,
        width=width,
        height=height,
        fps=fps,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
    )


def transcode_audio(input_path: Path, output_dir: Path, timeout: int = 1200) -> Path:
    """Transcode audio to 16kHz mono WAV for ASR.
    
    Per SPEC §6.2: 16kHz, mono, PCM s16le, with loudness normalization.
    
    Args:
        input_path: Input media file
        output_dir: Output directory
        
    Returns:
        Path to audio16k.wav
    """
    output_path = output_dir / "audio16k.wav"
    
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vn",  # No video
        "-ac", "1",  # Mono
        "-ar", "16000",  # 16kHz sample rate
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",  # EBU R128 normalization
        "-c:a", "pcm_s16le",
        "-y",  # Overwrite
        str(output_path),
    ]
    
    subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    
    return output_path


def transcode_analysis_video(input_path: Path, output_dir: Path, timeout: int = 1200) -> Path:
    """Transcode to analysis proxy: ≤720p, 15fps, H.264.
    
    Per SPEC §6.2: Efficient for CV processing.
    
    Args:
        input_path: Input media file
        output_dir: Output directory
        
    Returns:
        Path to analysis.mp4
    """
    output_path = output_dir / "analysis.mp4"
    
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vf", "scale='min(1280,iw)':-2,fps=15",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "26",
        "-an",  # No audio
        "-y",
        str(output_path),
    ]
    
    subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    
    return output_path


def extract_poster(input_path: Path, output_dir: Path, duration: float = 0) -> Path:
    """JPEG from the original, before the long playback transcode.

    Input seeking keeps this to about a second. The frame is 1s in, or 10%
    for a clip shorter than 1.5s.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    poster_path = output_dir / "poster.jpg"
    timestamp = 1.0 if duration >= 1.5 else max(0.0, float(duration) * 0.1)
    cmd = [
        "ffmpeg",
        "-ss", f"{timestamp:.3f}",
        "-i", str(input_path),
        "-frames:v", "1",
        "-q:v", "2",
        "-y",
        str(poster_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    return poster_path


def playback_ffmpeg_command(input_path: Path, playback_path: Path) -> List[str]:
    """H.264+AAC faststart at CRF 23. veryfast instead of medium.

    Same quality target as before. veryfast spends less time on a 1080p to
    720p playback rendition; the file can be a little larger.
    """
    return [
        "ffmpeg",
        "-i", str(input_path),
        "-vf", "scale='min(1280,iw)':-2",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y",
        str(playback_path),
    ]


def transcode_playback_video(input_path: Path, output_dir: Path, timeout: int = 1200) -> Path:
    """Transcode to playback proxy: H.264+AAC, faststart.

    The poster is extracted from the original earlier. This step does not
    wait on that frame.
    """
    playback_path = output_dir / "playback.mp4"
    cmd = playback_ffmpeg_command(input_path, playback_path)
    subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    return playback_path


def _generate_sprites_sequential(input_path: Path, sprites_dir: Path, duration: float) -> List[Path]:
    sprites: List[Path] = []
    num_sprites = int(duration / SPRITE_INTERVAL_SECONDS) + 1
    for i in range(num_sprites):
        timestamp = i * SPRITE_INTERVAL_SECONDS
        if timestamp >= duration:
            break
        sprite_path = sprites_dir / f"sprite_{i:04d}.jpg"
        cmd = [
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", str(input_path),
            "-vframes", "1",
            "-vf", "scale=160:-2",
            "-q:v", "5",
            "-y",
            str(sprite_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        sprites.append(sprite_path)
    return sprites


def generate_sprites(input_path: Path, output_dir: Path, duration: float) -> List[Path]:
    """Sprite thumbnails every 5 seconds (SPEC §6.2).

    One ffmpeg pass writes the series. A per-frame loop remains if that pass
    produces nothing, so a short or odd file still gets a preview.
    """
    sprites_dir = output_dir / "sprites"
    sprites_dir.mkdir(exist_ok=True)
    if duration <= 0:
        return []
    pattern = sprites_dir / "sprite_%04d.jpg"
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vf", f"fps=1/{SPRITE_INTERVAL_SECONDS},scale=160:-2",
        "-q:v", "5",
        "-start_number", "0",
        "-y",
        str(pattern),
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=transcode_timeout_s(duration, kind="sprites"),
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logger.warning("sprite pass failed; falling back to one frame at a time")
        return _generate_sprites_sequential(input_path, sprites_dir, duration)
    sprites = sorted(sprites_dir.glob("sprite_*.jpg"))
    if sprites:
        return sprites
    return _generate_sprites_sequential(input_path, sprites_dir, duration)


def _skin_ratio(bgr) -> float:
    """Share of pixels in a YCrCb skin band (heuristic, not identity)."""
    import cv2
    import numpy as np

    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
    return float(np.count_nonzero(mask)) / float(mask.size or 1)


def _mean_motion(grays) -> float:
    import cv2
    import numpy as np

    if len(grays) < 2:
        return 0.0
    diffs = [float(np.mean(cv2.absdiff(a, b))) / 255.0 for a, b in zip(grays, grays[1:])]
    return float(np.mean(diffs))


def score_person_presence(frames_bgr: list) -> float:
    """Combine skin-tone area and temporal motion into [0, 1].

    Appendix C C2: replaces the constant 0.8 placeholder. Screen-like
    frames (test patterns, slides) score low; a large moving skin blob scores high.
    """
    import cv2
    import numpy as np

    if len(frames_bgr) < 2:
        return 0.2
    skins = [_skin_ratio(frame) for frame in frames_bgr]
    grays = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames_bgr]
    skin = float(np.mean(skins))
    motion = _mean_motion(grays)
    skin_term = min(1.0, skin / 0.12) if skin >= 0.008 else 0.08
    motion_term = min(1.0, motion / 0.05)
    return max(0.0, min(1.0, 0.7 * skin_term + 0.3 * motion_term))


def detect_person_presence(video_path: Path, num_samples: int = 20) -> float:
    """Detect person presence in video using skin + motion heuristics.

    Samples frames and scores them. Higher = more likely a camera person
    is in frame; below 0.5 is treated as a screen recording.

    Args:
        video_path: Path to video file
        num_samples: Number of frames to sample

    Returns:
        Confidence score 0-1 (higher = more likely contains person)
    """
    import cv2

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_pattern = Path(tmpdir) / "sample_%03d.jpg"
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", f"fps=2,scale=160:-2",
                "-frames:v", str(max(2, num_samples)),
                "-q:v", "8",
                "-y",
                str(sample_pattern),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            samples = sorted(Path(tmpdir).glob("sample_*.jpg"))
            if len(samples) < 2:
                return 0.2
            frames = []
            for path in samples:
                image = cv2.imread(str(path))
                if image is not None:
                    frames.append(image)
            if len(frames) < 2:
                return 0.2
            return score_person_presence(frames)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return 0.3


def detect_modality(media_info: MediaInfo, analysis_video_path: Optional[Path]) -> ModalityFlags:
    """Detect modality: audio-only or screen recording.
    
    Per SPEC §6.2: Set flags for downstream processing.
    
    Args:
        media_info: Validated media information
        analysis_video_path: Path to analysis video (None if audio-only)
        
    Returns:
        ModalityFlags with detection results
    """
    is_audio_only = not media_info.has_video
    
    if is_audio_only:
        return ModalityFlags(
            is_audio_only=True,
            is_screen_recording=False,
            person_detection_confidence=0.0,
        )
    
    # Detect screen recording vs person video
    person_confidence = detect_person_presence(analysis_video_path)
    is_screen_recording = person_confidence < 0.5
    
    return ModalityFlags(
        is_audio_only=False,
        is_screen_recording=is_screen_recording,
        person_detection_confidence=person_confidence,
    )


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of file.
    
    Args:
        path: File path
        
    Returns:
        Hex digest of SHA256 hash
    """
    sha256 = hashlib.sha256()
    
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    
    return sha256.hexdigest()


def ingest(
    input_path: Path,
    output_dir: Path,
    session_id: str,
    on_progress: Optional[ProgressFn] = None,
    on_media: Optional[MediaFn] = None,
) -> IngestOutput:
    """Run complete ingest stage.
    
    Per SPEC §6.1, §6.2 and issue #17:
    1. Validate media with ffprobe
    2. Transcode to audio16k.wav, analysis.mp4, playback.mp4
    3. Generate sprites
    4. Detect modality (audio-only, screen recording)
    5. Return artifact paths and metadata
    
    Args:
        input_path: Path to uploaded media file
        output_dir: Directory for output artifacts
        session_id: Session ID for logging
        
    Returns:
        IngestOutput with all artifacts and metadata
        
    Raises:
        ValueError: If validation fails
        subprocess.CalledProcessError: If transcoding fails
    """
    logger.info(f"[{session_id}] Starting ingest: {input_path.name}")
    duration = 0.0

    def report(step: str, pct: float, artifact: Optional[str] = None) -> None:
        if on_progress is None:
            return
        eta = prepare_eta_s(duration, pct) if duration > 0 else None
        on_progress(step, pct, artifact, eta)

    # Step 1: Validate, then hash. The probe is what fills media duration.
    logger.info(f"[{session_id}] Validating media")
    media_info = validate_media(input_path)
    duration = float(media_info.duration or 0)
    if on_media is not None:
        on_media(media_info)
    sha256 = compute_file_hash(input_path)
    logger.info(f"[{session_id}] Input SHA256: {sha256}")
    report("ingest_check", 8)

    audio_timeout = transcode_timeout_s(duration, kind="audio")
    analysis_timeout = transcode_timeout_s(duration, kind="analysis")
    playback_timeout = transcode_timeout_s(duration, kind="playback")

    analysis_video_path = None
    artifacts: Dict[str, Path] = {}

    if media_info.has_video:
        # Poster from the original first, so the preview exists during the
        # long encodes instead of after them.
        logger.info(f"[{session_id}] Extracting poster")
        poster_path = extract_poster(input_path, output_dir, duration)
        artifacts["poster"] = poster_path
        report("ingest_poster", 10, "poster")

        logger.info(f"[{session_id}] Transcoding audio")
        report("ingest_audio", 16)
        audio_path = transcode_audio(input_path, output_dir, timeout=audio_timeout)
        artifacts["audio16k"] = audio_path

        logger.info(f"[{session_id}] Transcoding analysis video")
        report("ingest_analysis", 26)
        analysis_video_path = transcode_analysis_video(input_path, output_dir, timeout=analysis_timeout)
        artifacts["analysis"] = analysis_video_path

        logger.info(f"[{session_id}] Transcoding playback video")
        report("ingest_playback", 36)
        playback_path = transcode_playback_video(input_path, output_dir, timeout=playback_timeout)
        artifacts["playback"] = playback_path

        logger.info(f"[{session_id}] Generating sprites")
        report("ingest_sprites", 39)
        sprites = generate_sprites(playback_path, output_dir, duration)
        logger.info(f"[{session_id}] Generated {len(sprites)} sprites")
    else:
        logger.info(f"[{session_id}] Transcoding audio")
        report("ingest_audio", 20)
        audio_path = transcode_audio(input_path, output_dir, timeout=audio_timeout)
        artifacts["audio16k"] = audio_path

    logger.info(f"[{session_id}] Detecting modality")
    report("ingest_modality", 40)
    modality = detect_modality(media_info, analysis_video_path)
    
    logger.info(
        f"[{session_id}] Ingest complete: "
        f"audio_only={modality.is_audio_only}, "
        f"screen_recording={modality.is_screen_recording}"
    )
    
    return IngestOutput(
        media_info=media_info,
        modality=modality,
        artifacts=artifacts,
        sha256=sha256,
    )
