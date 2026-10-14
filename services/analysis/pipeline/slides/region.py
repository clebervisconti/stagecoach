"""Slide-region detection (SPEC §6.6 step 1). Heuristic (H). CPU only."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

# Stage: large bright low-motion quadrilateral (H).
BRIGHT = 170.0
MOTION = 18.0
MIN_AREA_RATIO = 0.12


def full_frame_region(width: int, height: int) -> dict[str, int]:
    return {"x": 0, "y": 0, "w": int(width), "h": int(height)}


def detect_slide_region(
    frames_bgr: list[np.ndarray],
    *,
    setup: str = "unknown",
    is_screen_recording: bool = False,
) -> dict[str, Any]:
    """Return {x,y,w,h, method}. Screen recordings use the full frame."""
    if not frames_bgr:
        return {**full_frame_region(1, 1), "method": "empty"}
    height, width = frames_bgr[0].shape[:2]
    full = {**full_frame_region(width, height), "method": "full_frame"}
    if is_screen_recording or setup == "screen_recording":
        full["method"] = "screen_recording_full_frame"
        return full
    if setup != "stage" or len(frames_bgr) < 2:
        return full

    gray = [np.mean(f.astype(np.float32), axis=2) for f in frames_bgr[:12]]
    luma = np.mean(np.stack(gray, axis=0), axis=0)
    diffs = [np.abs(gray[i] - gray[i - 1]) for i in range(1, len(gray))]
    motion = np.mean(np.stack(diffs, axis=0), axis=0) if diffs else np.zeros_like(luma)
    mask = (luma >= BRIGHT) & (motion <= MOTION)
    if float(np.mean(mask)) < MIN_AREA_RATIO:
        return full
    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    w, h = x1 - x0, y1 - y0
    if w * h < MIN_AREA_RATIO * width * height:
        return full
    # Prefer a rectangle that looks like a projection screen (not a tiny lamp).
    aspect = w / max(h, 1)
    if aspect < 0.8 or aspect > 3.5:
        return full
    return {"x": x0, "y": y0, "w": w, "h": h, "method": "stage_bright_quad_h"}
