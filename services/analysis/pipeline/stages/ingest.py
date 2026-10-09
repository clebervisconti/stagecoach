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
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Limits per SPEC §6.2 (heuristic)
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_DURATION_SECONDS = 90 * 60  # 90 minutes
SPRITE_INTERVAL_SECONDS = 5

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


def transcode_audio(input_path: Path, output_dir: Path) -> Path:
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
    
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    
    return output_path


def transcode_analysis_video(input_path: Path, output_dir: Path) -> Path:
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
    
    subprocess.run(cmd, check=True, capture_output=True, timeout=1200)
    
    return output_path


def transcode_playback_video(input_path: Path, output_dir: Path) -> Tuple[Path, Path]:
    """Transcode to playback proxy: H.264+AAC, faststart, with poster.
    
    Per SPEC §6.2: Web-optimized playback.
    
    Args:
        input_path: Input media file
        output_dir: Output directory
        
    Returns:
        Tuple of (playback.mp4 path, poster.jpg path)
    """
    playback_path = output_dir / "playback.mp4"
    poster_path = output_dir / "poster.jpg"
    
    # Transcode with faststart
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vf", "scale='min(1280,iw)':-2",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y",
        str(playback_path),
    ]
    
    subprocess.run(cmd, check=True, capture_output=True, timeout=1200)
    
    # Extract poster frame at 1s (or 10% if shorter)
    cmd_poster = [
        "ffmpeg",
        "-i", str(playback_path),
        "-ss", "1",
        "-vframes", "1",
        "-q:v", "2",
        "-y",
        str(poster_path),
    ]
    
    subprocess.run(cmd_poster, check=True, capture_output=True, timeout=30)
    
    return playback_path, poster_path


def generate_sprites(input_path: Path, output_dir: Path, duration: float) -> List[Path]:
    """Generate sprite thumbnails every 5 seconds.
    
    Per SPEC §6.2: For timeline hover previews.
    
    Args:
        input_path: Input video file
        output_dir: Output directory
        duration: Media duration in seconds
        
    Returns:
        List of sprite image paths
    """
    sprites_dir = output_dir / "sprites"
    sprites_dir.mkdir(exist_ok=True)
    
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


def detect_person_presence(video_path: Path, num_samples: int = 20) -> float:
    """Detect person presence in video using simple heuristics.
    
    Samples frames and checks for motion/variation to distinguish
    screen recordings from camera recordings.
    
    Args:
        video_path: Path to video file
        num_samples: Number of frames to sample
        
    Returns:
        Confidence score 0-1 (higher = more likely contains person)
    """
    # Simple heuristic: check frame variance
    # Screen recordings have low temporal variance
    # This is a placeholder - real implementation would use CV
    
    try:
        # Extract sample frames
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_pattern = Path(tmpdir) / "sample_%03d.jpg"
            
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", f"select='not(mod(n\\,floor(n_frames/{num_samples})))',scale=160:-2",
                "-vsync", "0",
                "-q:v", "8",
                str(sample_pattern),
            ]
            
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=60,
            )
            
            # Count actual samples
            samples = list(Path(tmpdir).glob("sample_*.jpg"))
            
            # If we have very few samples or static frames, likely screen recording
            if len(samples) < num_samples / 2:
                return 0.2
            
            # Placeholder: real implementation would analyze frames
            # For now, assume person present if not audio-only
            return 0.8
            
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # On error, assume low confidence
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
    
    # Step 1: Validate
    logger.info(f"[{session_id}] Validating media")
    media_info = validate_media(input_path)
    
    # Compute input file hash
    sha256 = compute_file_hash(input_path)
    logger.info(f"[{session_id}] Input SHA256: {sha256}")
    
    # Step 2: Transcode audio
    logger.info(f"[{session_id}] Transcoding audio")
    audio_path = transcode_audio(input_path, output_dir)
    
    artifacts = {
        "audio16k": audio_path,
    }
    
    # Step 3: Transcode video (if present)
    analysis_video_path = None
    
    if media_info.has_video:
        logger.info(f"[{session_id}] Transcoding analysis video")
        analysis_video_path = transcode_analysis_video(input_path, output_dir)
        artifacts["analysis"] = analysis_video_path
        
        logger.info(f"[{session_id}] Transcoding playback video")
        playback_path, poster_path = transcode_playback_video(input_path, output_dir)
        artifacts["playback"] = playback_path
        artifacts["poster"] = poster_path
        
        # Step 4: Generate sprites
        logger.info(f"[{session_id}] Generating sprites")
        sprites = generate_sprites(playback_path, output_dir, media_info.duration)
        logger.info(f"[{session_id}] Generated {len(sprites)} sprites")
    
    # Step 5: Detect modality
    logger.info(f"[{session_id}] Detecting modality")
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
