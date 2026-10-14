"""Decode the 15-fps analysis proxy with ffmpeg (CPU, no OpenCV GUI)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterator

import numpy as np


def probe_video(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    return json.loads(proc.stdout.decode())


def video_size(path: Path) -> tuple[int, int, float]:
    info = probe_video(path)
    stream = next(s for s in info["streams"] if s.get("codec_type") == "video")
    width = int(stream["width"])
    height = int(stream["height"])
    fps_txt = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "15/1"
    num, _, den = fps_txt.partition("/")
    fps = float(num) / float(den or "1")
    if fps <= 0:
        fps = 15.0
    return width, height, fps


def iter_rgb_frames(path: Path) -> Iterator[tuple[int, float, np.ndarray]]:
    """Yield (frame_index, t_seconds, HxWx3 uint8 RGB)."""
    width, height, fps = video_size(path)
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-an",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    frame_bytes = width * height * 3
    index = 0
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                break
            frame = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 3))
            yield index, index / fps, frame
            index += 1
    finally:
        proc.kill()
        proc.wait(timeout=5)
