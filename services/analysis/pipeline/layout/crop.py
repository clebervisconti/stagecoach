"""Cut camera.mp4 and screen.mp4 from the original (spec §9.3)."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _region_for(layout: dict[str, Any], role: str) -> Optional[dict[str, Any]]:
    for segment in layout.get("segments") or []:
        for region in segment.get("regions") or []:
            if region.get("role") == role:
                return {**region, "t_start": segment.get("t_start", 0.0), "t_end": segment.get("t_end")}
    return None


def _pixel_crop(region: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    x = max(0, int(round(float(region["x"]) * width)))
    y = max(0, int(round(float(region["y"]) * height)))
    w = max(2, int(round(float(region["w"]) * width)))
    h = max(2, int(round(float(region["h"]) * height)))
    w -= w % 2
    h -= h % 2
    if x + w > width:
        x = max(0, width - w)
    if y + h > height:
        y = max(0, height - h)
    return x, y, w, h


def _run_crop(
    original: Path,
    dest: Path,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    t0: float,
    t1: Optional[float],
    scale: str,
    fps: int,
    with_audio: bool = False,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = f"crop={w}:{h}:{x}:{y},scale={scale},fps={fps}"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, t0):.3f}",
        "-i",
        str(original),
    ]
    if t1 is not None and t1 > t0:
        cmd.extend(["-to", f"{t1:.3f}"])
    cmd.extend(["-vf", vf])
    if not with_audio:
        cmd.append("-an")
    cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-y", str(dest)])
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def write_region_tracks(
    original: Path,
    output_dir: Path,
    layout: dict[str, Any],
    *,
    frame_width: int,
    frame_height: int,
) -> dict[str, Any]:
    """Produce camera.mp4 / screen.mp4 and span sidecars from the original file."""
    artifacts: dict[str, Any] = {}
    for role, scale, fps in (
        ("camera", "min(720\\,iw):-2", 15),
        ("screen", "min(1920\\,iw):-2", 5),
    ):
        region = _region_for(layout, role)
        if not region:
            continue
        x, y, w, h = _pixel_crop(region, frame_width, frame_height)
        dest = output_dir / f"{role}.mp4"
        t0 = float(region.get("t_start") or 0.0)
        t1 = region.get("t_end")
        t1_f = float(t1) if t1 is not None else None
        _run_crop(original, dest, x=x, y=y, w=w, h=h, t0=t0, t1=t1_f, scale=scale, fps=fps)
        spans = [{"t0": t0, "t1": t1_f, "src_t0": t0, "src_t1": t1_f}]
        spans_path = output_dir / f"{role}_spans.json"
        spans_path.write_text(json.dumps(spans, indent=2) + "\n")
        artifacts[role] = str(dest)
        artifacts[f"{role}_spans"] = str(spans_path)
        artifacts[f"{role}_px"] = {"x": x, "y": y, "w": w, "h": h}
        if role == "camera":
            from pipeline.layout.face_visibility import write_camera_face_quality

            try:
                quality = write_camera_face_quality(dest, output_dir)
            except Exception as exc:
                logger.warning("camera face visibility failed: %s", exc)
                quality = None
            if quality is not None:
                artifacts["camera_face_quality"] = str(output_dir / "camera_face_quality.json")
                artifacts["face_visible_ratio"] = quality["face_visible_ratio"]
    return artifacts
