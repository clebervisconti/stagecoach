"""Camera-tile and screen-rectangle helpers (spec §9.2.4)."""

from __future__ import annotations

from typing import Optional

import numpy as np

from pipeline.layout.faces import FaceDetection

ASPECTS = (16 / 9, 4 / 3, 1.0, 9 / 16)


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def clamp_norm(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    w = min(max(w, 0.05), 1.0 - x)
    h = min(max(h, 0.05), 1.0 - y)
    return x, y, w, h


def snap_aspect(w: float, h: float) -> tuple[float, float]:
    if h <= 0:
        return w, h
    current = w / h
    best = min(ASPECTS, key=lambda a: abs(a - current))
    if abs(best - current) / current <= 0.06:
        return h * best, h
    return w, h


def grow_tile(
    frame_bgr: np.ndarray,
    face: FaceDetection,
    *,
    max_w_scale: float = 4.0,
    max_h_scale: float = 4.5,
) -> tuple[float, float, float, float]:
    """Grow a face box to the surrounding tile by luma discontinuity.

    Works on the synthetic PiP fixtures (solid tile on a dark field) and on
    real composites whose tile is a distinct rectangle.
    """
    height, width = frame_bgr.shape[:2]
    gray = np.mean(frame_bgr, axis=2)
    fx, fy, fw, fh = face.x, face.y, face.w, face.h
    x0 = int(max(0, fx))
    y0 = int(max(0, fy))
    x1 = int(min(width, fx + fw))
    y1 = int(min(height, fy + fh))
    if x1 <= x0 or y1 <= y0:
        return clamp_norm(fx / width, fy / height, fw / width, fh / height)
    interior = float(np.median(gray[y0:y1, x0:x1]))
    threshold = max(18.0, interior * 0.35)

    def col_ok(x: int) -> bool:
        if x < 0 or x >= width:
            return False
        band = gray[y0:y1, x]
        return float(np.median(band)) >= interior - threshold

    def row_ok(y: int) -> bool:
        if y < 0 or y >= height:
            return False
        band = gray[y, x0:x1]
        return float(np.median(band)) >= interior - threshold

    left, right, top, bottom = x0, x1 - 1, y0, y1 - 1
    max_w = int(fw * max_w_scale)
    max_h = int(fh * max_h_scale)
    while left > 0 and (right - left) < max_w and col_ok(left - 1):
        left -= 1
    while right < width - 1 and (right - left) < max_w and col_ok(right + 1):
        right += 1
    while top > 0 and (bottom - top) < max_h and row_ok(top - 1):
        top -= 1
    while bottom < height - 1 and (bottom - top) < max_h and row_ok(bottom + 1):
        bottom += 1

    tw = max(1, right - left + 1)
    th = max(1, bottom - top + 1)
    nx, ny = left / width, top / height
    nw, nh = tw / width, th / height
    nw, nh = snap_aspect(nw, nh)
    return clamp_norm(nx, ny, nw, nh)


def fallback_tile(face: FaceDetection, frame_w: int, frame_h: int) -> tuple[float, float, float, float]:
    w = face.w * 3.0
    h = face.h * 3.6
    x = face.x + face.w / 2 - w / 2
    y = face.y + face.h * 0.4 - h * 0.4
    return clamp_norm(x / frame_w, y / frame_h, w / frame_w, h / frame_h)


def screen_in_complement(
    camera: Optional[tuple[float, float, float, float]],
) -> Optional[tuple[float, float, float, float]]:
    """Largest axis-aligned rectangle in the complement of the camera tile."""
    if camera is None:
        return (0.0, 0.0, 1.0, 1.0)
    cx, cy, cw, ch = camera
    candidates = [
        (0.0, 0.0, cx, 1.0),
        (cx + cw, 0.0, 1.0 - (cx + cw), 1.0),
        (0.0, 0.0, 1.0, cy),
        (0.0, cy + ch, 1.0, 1.0 - (cy + ch)),
    ]
    best = None
    best_area = 0.0
    for x, y, w, h in candidates:
        if w < 0.20 or h < 0.20:
            continue
        area = w * h
        if area > best_area:
            best = clamp_norm(x, y, w, h)
            best_area = area
    return best
