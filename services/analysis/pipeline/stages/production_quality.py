"""Cheap production-quality signals (spec §9.8). No consent required."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

STAGE_VERSION = "1.0.0"

# libebur128 prints -70.0 LUFS when the absolute gate has no signal yet, and
# again in the summary when the whole stream is below that gate. It is not a
# loudness measurement.
LUFS_SILENCE_FLOOR = -70.0


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


def parse_ebur128(text: str) -> tuple[Optional[float], Optional[float]]:
    """Integrated loudness and true peak from an ffmpeg ebur128 log.

    Progress lines print ``I:`` from the first frame, which is the -70 LUFS
    floor until enough audio is gated in. The summary block is the measurement.
    """
    summary = text
    marker = text.rfind("Summary:")
    if marker >= 0:
        summary = text[marker:]
    integrated = None
    block = re.search(
        r"Integrated loudness:\s+I:\s*(-?[\d.]+)\s*LUFS",
        summary,
        flags=re.S,
    )
    if block:
        integrated = float(block.group(1))
    else:
        found = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", summary)
        if found:
            integrated = float(found[-1])
    peak = None
    peaks = re.findall(r"Peak:\s*(-?[\d.]+)\s*dBFS", summary)
    if not peaks:
        peaks = re.findall(r"True peak:\s*(-?[\d.]+)\s*dBTP", summary, flags=re.I)
    if peaks:
        peak = float(peaks[-1])
    return _reject_silence_floor(integrated), peak


def _reject_silence_floor(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= LUFS_SILENCE_FLOOR:
        return None
    return value


def _ebur128(audio_or_video: Path, audio_ordinal: Optional[int] = None) -> tuple[Optional[float], Optional[float]]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(audio_or_video),
    ]
    if audio_ordinal is not None:
        cmd.extend(["-map", f"0:a:{audio_ordinal}"])
    cmd.extend(
        [
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ]
    )
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return None, None
    return parse_ebur128(result.stderr or "")


def _audio_stream_count(path: Path) -> int:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return 0
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def _measure_loudness(path: Path) -> tuple[Optional[float], Optional[float]]:
    """Loudness of the speech stream, not a silent companion track.

    The analysis WAV is loudness-normalised, so it is not a production measurement.
    A webinar file often puts silence on the first audio stream and speech on another.
    """
    lufs, peak = _ebur128(path)
    if lufs is not None:
        return lufs, peak
    count = _audio_stream_count(path)
    for ordinal in range(count):
        measured_lufs, measured_peak = _ebur128(path, audio_ordinal=ordinal)
        if measured_lufs is not None:
            return measured_lufs, measured_peak
    return None, None


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


def _metric(
    mid: str,
    value: Any,
    unit: str,
    confidence: float = 0.85,
    applicable: bool = True,
    failure_mode: Optional[str] = None,
) -> dict[str, Any]:
    missing = value is None
    return {
        "id": mid,
        "value": value,
        "unit": unit,
        "confidence": confidence,
        "applicable": applicable and not missing,
        "basis": "heuristic",
        "source": "H" if mid in {"pq_snr_db", "pq_clipping_ratio", "pq_frozen_video_s"} else "S69",
        "failure_mode": (failure_mode or "missing_input") if missing else None,
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
    # audio16k.wav is EBU-normalised for ASR. Measuring it would report the
    # target loudness, not the recording. A missing original stays unmeasured.
    if media_path.is_file():
        lufs, peak = _measure_loudness(media_path)
    else:
        lufs, peak = None, None
    clipping = _clipping_ratio(audio16k if audio16k.is_file() else media_path)
    frozen = _frozen_seconds(camera_path or (output_dir / "camera.mp4"))
    snr = None
    if audio_metrics and audio_metrics.get("snr_db") is not None:
        snr = float(audio_metrics["snr_db"])
    height = source_height if source_height is not None else _ffprobe_height(media_path)

    payload = {
        "version": STAGE_VERSION,
        "metrics": [
            _metric("pq_snr_db", snr, "dB"),
            _metric(
                "pq_integrated_lufs",
                lufs,
                "LUFS",
                failure_mode=None if lufs is not None else "silence_floor",
            ),
            _metric("pq_clipping_ratio", clipping, "ratio"),
            _metric("pq_frozen_video_s", frozen, "seconds"),
            _metric("pq_true_peak_dbtp", peak, "dBTP"),
            _metric("pq_source_height_px", height, "px", confidence=1.0),
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "production_quality.json"
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
