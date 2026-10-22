"""Cheap production-quality signals (spec §9.8). No consent required."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

STAGE_VERSION = "1.0.0"


def _ffprobe_height(path: Path) -> Optional[int]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=height",
        "-of",
        "csv=p=0",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        raw = result.stdout.strip().split("\n")[0]
        return int(raw) if raw else None
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return None


def _ebur128(audio_or_video: Path) -> tuple[Optional[float], Optional[float]]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(audio_or_video),
        "-af",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return None, None
    text = result.stderr or ""
    integrated = None
    peak = None
    match_i = re.search(r"I:\s*(-?[\d.]+)\s*LUFS", text)
    if match_i:
        integrated = float(match_i.group(1))
    match_p = re.search(r"Peak:\s*(-?[\d.]+)\s*dBFS", text) or re.search(
        r"True peak:\s*(-?[\d.]+)\s*dBTP", text, flags=re.I
    )
    if match_p:
        peak = float(match_p.group(1))
    return integrated, peak


def _clipping_ratio(audio_path: Path) -> Optional[float]:
    if not audio_path.is_file():
        return None
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        "48000",
        "-f",
        "s16le",
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=90)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    raw = result.stdout
    if len(raw) < 2:
        return None
    import numpy as np

    samples = np.frombuffer(raw, dtype=np.int16)
    if samples.size == 0:
        return None
    clipped = np.mean(np.abs(samples) >= 32766)
    return float(clipped)


def _frozen_seconds(video_path: Path) -> float:
    if not video_path.is_file():
        return 0.0
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video_path),
        "-vf",
        "freezedetect=n=0.003:d=2",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 0.0
    total = 0.0
    for match in re.finditer(r"freeze_duration:\s*([\d.]+)", result.stderr or ""):
        total += float(match.group(1))
    return total


def _metric(mid: str, value: Any, unit: str, confidence: float = 0.85, applicable: bool = True) -> dict[str, Any]:
    return {
        "id": mid,
        "value": value,
        "unit": unit,
        "confidence": confidence,
        "applicable": applicable and value is not None,
        "basis": "heuristic",
        "source": "H" if mid in {"pq_snr_db", "pq_clipping_ratio", "pq_frozen_video_s"} else "S69",
        "failure_mode": None if value is not None else "missing_input",
    }


def run_production_quality(
    *,
    output_dir: Path,
    media_path: Path,
    audio_metrics: Optional[dict[str, Any]] = None,
    camera_path: Optional[Path] = None,
    source_height: Optional[int] = None,
) -> dict[str, Any]:
    audio16k = output_dir / "audio16k.wav"
    probe = media_path if media_path.is_file() else audio16k
    lufs, peak = _ebur128(probe)
    clipping = _clipping_ratio(audio16k if audio16k.is_file() else probe)
    frozen = _frozen_seconds(camera_path or (output_dir / "camera.mp4"))
    snr = None
    if audio_metrics and audio_metrics.get("snr_db") is not None:
        snr = float(audio_metrics["snr_db"])
    height = source_height if source_height is not None else _ffprobe_height(media_path)

    payload = {
        "version": STAGE_VERSION,
        "metrics": [
            _metric("pq_snr_db", snr, "dB"),
            _metric("pq_integrated_lufs", lufs, "LUFS"),
            _metric("pq_clipping_ratio", clipping, "ratio"),
            _metric("pq_frozen_video_s", frozen, "seconds"),
            _metric("pq_true_peak_dbtp", peak, "dBTP"),
            _metric("pq_source_height_px", height, "px", confidence=1.0),
        ],
    }
    dest = output_dir / "production_quality.json"
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
