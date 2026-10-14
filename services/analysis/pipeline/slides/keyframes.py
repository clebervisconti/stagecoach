"""Keyframe = sharpest frame (Laplacian variance) in the first half of the segment (SPEC §6.6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


def laplacian_var(gray: np.ndarray) -> float:
    if cv2 is None:
        return float(np.var(gray.astype(np.float64)))
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def crop_bgr(frame: np.ndarray, region: Optional[dict[str, int]]) -> np.ndarray:
    if not region:
        return frame
    x, y, w, h = int(region["x"]), int(region["y"]), int(region["w"]), int(region["h"])
    y2, x2 = y + max(h, 1), x + max(w, 1)
    return frame[y:y2, x:x2]


def extract_keyframe(
    video_path: Path,
    start_s: float,
    end_s: float,
    dest: Path,
    *,
    region: Optional[dict[str, int]] = None,
    sample_fps: float = 5.0,
) -> dict[str, Any]:
    """Write the sharpest first-half frame to `dest`. Synthetic/CC0 media only in tests."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(end_s - start_s, 0.04)
    half_end = start_s + duration / 2.0
    best_score = -1.0
    best_t = start_s
    best = None
    if cv2 is None:
        dest.write_bytes(b"")
        return {"path": str(dest), "t": start_s, "sharpness": None, "error": "opencv_missing"}

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"path": None, "t": start_s, "sharpness": None, "error": "open_failed"}
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    step = max(int(round(fps / sample_fps)), 1)
    start_frame = int(round(start_s * fps))
    end_frame = int(round(half_end * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    idx = start_frame
    while idx <= end_frame:
        ok, frame = cap.read()
        if not ok:
            break
        if (idx - start_frame) % step != 0:
            idx += 1
            continue
        crop = crop_bgr(frame, region)
        if crop.size == 0:
            idx += 1
            continue
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        score = laplacian_var(gray)
        if score > best_score:
            best_score = score
            best = crop
            best_t = idx / fps
        idx += 1
    cap.release()
    if best is None:
        return {"path": None, "t": start_s, "sharpness": None, "error": "no_frame"}
    cv2.imwrite(str(dest), best)
    return {"path": str(dest), "t": round(best_t, 3), "sharpness": round(best_score, 2), "error": None}
