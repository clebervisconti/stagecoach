"""1 Hz screen activity classes (spec §9.5.1, E3-1).

Frames are downscaled to 640 px wide, converted to gray, and blurred with
σ = 1. A second is the change between frames one second apart.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from pipeline.screen.transitions import ssim_gray

CHANGED_DELTA = 12
STATIC_RATIO = 0.002
POINTER_RATIO = 0.02
POINTER_BBOX = 0.03
SCROLL_RATIO = 0.02
SCROLL_SHIFT_PX = 8.0
# Coherent translation, not a cut between unrelated frames. Tuned on synthetic
# stripes; recorded in ADR-089.
SCROLL_RESPONSE_MIN = 0.12
TYPING_RATIO_MIN = 0.002
TYPING_RATIO_MAX = 0.05
TYPING_ASPECT = 4.0
TYPING_PERSIST_S = 3
CONTENT_RATIO = 0.30
TARGET_WIDTH = 640


def prepare_gray(frame: np.ndarray, width: int = TARGET_WIDTH) -> np.ndarray:
    """Gray, 640 px wide, Gaussian blur σ = 1."""
    import cv2

    image = frame
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image = np.ascontiguousarray(image)
    h, w = image.shape[:2]
    if w != width and w > 0:
        new_h = max(2, int(round(h * (width / float(w)))))
        if new_h % 2:
            new_h += 1
        image = cv2.resize(image, (width, new_h), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(image, (0, 0), 1.0)


def _down_320(gray: np.ndarray) -> np.ndarray:
    import cv2

    h, w = gray.shape[:2]
    if w <= 320:
        return gray
    new_h = max(2, int(round(h * (320.0 / float(w)))))
    return cv2.resize(gray, (320, new_h), interpolation=cv2.INTER_AREA)


def _geometry(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return 0.0, 0.0
    box_w = float(xs.max() - xs.min() + 1)
    box_h = float(ys.max() - ys.min() + 1)
    area = (box_w * box_h) / float(mask.size)
    aspect = box_w / max(box_h, 1.0)
    return float(area), float(aspect)


def _vertical_shift(prev: np.ndarray, curr: np.ndarray) -> tuple[float, float]:
    import cv2

    try:
        shift, response = cv2.phaseCorrelate(prev.astype(np.float32), curr.astype(np.float32))
    except cv2.error:
        return 0.0, 0.0
    if shift is None or len(shift) < 2:
        return 0.0, 0.0
    dy = float(shift[1])
    resp = float(response)
    if not np.isfinite(dy) or not np.isfinite(resp):
        return 0.0, 0.0
    return abs(dy), resp


def provisional_class(changed_ratio: float, bbox_area: float, aspect: float, v_shift: float, v_response: float) -> str:
    """One second, before the typing-persistence pass.

    A coherent vertical shift is scroll even when most pixels move. An unrelated
    cut rarely has a high phase-correlation response, so it stays content_change.
    """
    if changed_ratio < STATIC_RATIO:
        return "static"
    if (
        changed_ratio >= SCROLL_RATIO
        and v_shift >= SCROLL_SHIFT_PX
        and v_response >= SCROLL_RESPONSE_MIN
    ):
        return "scroll"
    if changed_ratio >= CONTENT_RATIO:
        return "content_change"
    if TYPING_RATIO_MIN <= changed_ratio <= TYPING_RATIO_MAX and aspect >= TYPING_ASPECT:
        return "typing_candidate"
    if changed_ratio < POINTER_RATIO and bbox_area < POINTER_BBOX:
        return "pointer"
    return "motion"


def measure_pair(prev: np.ndarray, curr: np.ndarray, t: float) -> dict[str, Any]:
    import cv2

    delta = cv2.absdiff(prev, curr)
    raw = delta > CHANGED_DELTA
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, kernel)
    changed_ratio = float(raw.mean())
    bbox_area, aspect = _geometry(opened)
    v_shift, v_response = _vertical_shift(prev, curr)
    cls = provisional_class(changed_ratio, bbox_area, aspect, v_shift, v_response)
    return {
        "t": round(float(t), 3),
        "changed_ratio": round(changed_ratio, 6),
        "bbox_area": round(bbox_area, 6),
        "aspect": round(aspect, 4),
        "v_shift": round(v_shift, 3),
        "v_response": round(v_response, 4),
        "cls": cls,
        "ssim_prev": 1.0,
    }


def finalize_classes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Promote a typing candidate only when the thin band persists ≥ 3 s."""
    i = 0
    while i < len(rows):
        if rows[i]["cls"] != "typing_candidate":
            i += 1
            continue
        j = i
        while j < len(rows) and rows[j]["cls"] == "typing_candidate":
            j += 1
        label = "typing" if (j - i) >= TYPING_PERSIST_S else "motion"
        for k in range(i, j):
            rows[k]["cls"] = label
        i = j
    return rows


def activity_from_grays(frames: list[np.ndarray], times: Optional[list[float]] = None) -> list[dict[str, Any]]:
    """Classify a 1 Hz gray (or BGR) sequence. `times` are the frame timestamps."""
    if times is None:
        times = [float(i) for i in range(len(frames))]
    rows: list[dict[str, Any]] = []
    prev = None
    prev_small = None
    for frame, t in zip(frames, times):
        gray = prepare_gray(frame)
        small = _down_320(gray)
        if prev is not None and prev_small is not None:
            row = measure_pair(prev, gray, float(t))
            row["ssim_prev"] = round(ssim_gray(prev_small, small), 4)
            rows.append(row)
        prev = gray
        prev_small = small
    return finalize_classes(rows)


def activity_from_video(
    path: Path,
    *,
    deadline: Optional[float] = None,
    width: int = TARGET_WIDTH,
) -> tuple[list[dict[str, Any]], float, bool]:
    """Sample `path` at 1 Hz. Returns rows, duration, and whether the budget stopped the pass."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return [], 0.0, False
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 5.0
    count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    duration = count / fps if fps else 0.0
    rows: list[dict[str, Any]] = []
    prev = None
    prev_small = None
    t = 0.0
    truncated = False
    while duration <= 0 or t < duration - 0.05:
        if deadline is not None and time.monotonic() > deadline:
            truncated = True
            break
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            break
        gray = prepare_gray(frame, width)
        small = _down_320(gray)
        if prev is not None and prev_small is not None:
            row = measure_pair(prev, gray, t)
            row["ssim_prev"] = round(ssim_gray(prev_small, small), 4)
            rows.append(row)
        prev = gray
        prev_small = small
        t += 1.0
        if duration <= 0 and t > 3600:
            break
    cap.release()
    if duration <= 0 and rows:
        duration = float(rows[-1]["t"]) + 1.0
    return finalize_classes(rows), float(duration), truncated


def write_activity_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    """Columns required by §9.5.1: t, changed_ratio, bbox_area, cls."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "t": pa.array([float(r["t"]) for r in rows], type=pa.float64()),
            "changed_ratio": pa.array([float(r["changed_ratio"]) for r in rows], type=pa.float64()),
            "bbox_area": pa.array([float(r["bbox_area"]) for r in rows], type=pa.float64()),
            "cls": pa.array([str(r["cls"]) for r in rows], type=pa.string()),
        }
    )
    pq.write_table(table, path)


def read_activity_parquet(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    data = table.to_pydict()
    rows = []
    for i in range(table.num_rows):
        rows.append(
            {
                "t": float(data["t"][i]),
                "changed_ratio": float(data["changed_ratio"][i]),
                "bbox_area": float(data["bbox_area"][i]),
                "cls": str(data["cls"][i]),
            }
        )
    return rows
