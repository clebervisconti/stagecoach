"""Frame sampling for layout detection (spec §9.2.1)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SAMPLE_FPS = 0.5
SAMPLE_WIDTH = 960
MAX_SAMPLES = 1800
CHUNK = 200


@dataclass(frozen=True)
class SampledFrame:
    t: float
    bgr: np.ndarray
    gray: np.ndarray


def _probe_size(video_path: Path) -> tuple[int, int]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    width_s, height_s = result.stdout.strip().split(",")
    return int(width_s), int(height_s)


def sample_frames(
    video_path: Path,
    *,
    fps: float = SAMPLE_FPS,
    width: int = SAMPLE_WIDTH,
    max_frames: int = MAX_SAMPLES,
) -> list[SampledFrame]:
    """Decode at `fps`, scaled to `width` px. Never keeps more than `max_frames`."""
    src_w, src_h = _probe_size(video_path)
    if src_w <= 0 or src_h <= 0:
        return []
    out_h = max(2, int(round(src_h * (width / src_w) / 2) * 2))
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps},scale={width}:{out_h}",
        "-frames:v",
        str(max_frames),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False, timeout=180)
    raw = proc.stdout
    frame_bytes = width * out_h * 3
    if frame_bytes <= 0 or not raw:
        return []
    count = min(len(raw) // frame_bytes, max_frames)
    frames: list[SampledFrame] = []
    for index in range(count):
        chunk = raw[index * frame_bytes : (index + 1) * frame_bytes]
        bgr = np.frombuffer(chunk, dtype=np.uint8).reshape((out_h, width, 3)).copy()
        gray = np.mean(bgr, axis=2).astype(np.uint8)
        frames.append(SampledFrame(t=index / fps if fps else 0.0, bgr=bgr, gray=gray))
    return frames


def extract_preview_jpeg(
    video_path: Path,
    dest: Path,
    *,
    t: float,
    width: int = 640,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, t):.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:-2",
        "-q:v",
        "4",
        "-y",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    return dest
