"""SSIM + PySceneDetect transitions, debounced (spec §9.5.2, E3-2).

SSIM is a Gaussian-window implementation on 320 px gray frames. No new
dependency: OpenCV and numpy only.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from pipeline.slides.scenes import MERGE_GAP_S

SSIM_CUT = 0.85
SSIM_STABLE = 0.95
STABLE_S = 2.0
BBOX_MIN = 0.25
SUPPRESS_CLASSES = frozenset({"scroll", "typing"})


def ssim_gray(a: np.ndarray, b: np.ndarray) -> float:
    """Mean SSIM of two gray frames. Sizes must match."""
    import cv2

    if a.shape != b.shape or a.size == 0:
        return 0.0
    x = a.astype(np.float64)
    y = b.astype(np.float64)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mu_x = cv2.GaussianBlur(x, (11, 11), 1.5)
    mu_y = cv2.GaussianBlur(y, (11, 11), 1.5)
    mu_x2 = mu_x * mu_x
    mu_y2 = mu_y * mu_y
    mu_xy = mu_x * mu_y
    sigma_x2 = cv2.GaussianBlur(x * x, (11, 11), 1.5) - mu_x2
    sigma_y2 = cv2.GaussianBlur(y * y, (11, 11), 1.5) - mu_y2
    sigma_xy = cv2.GaussianBlur(x * y, (11, 11), 1.5) - mu_xy
    num = (2.0 * mu_xy + c1) * (2.0 * sigma_xy + c2)
    den = (mu_x2 + mu_y2 + c1) * (sigma_x2 + sigma_y2 + c2)
    den = np.where(den == 0, 1.0, den)
    score = float(np.mean(num / den))
    if not np.isfinite(score):
        return 0.0
    return max(0.0, min(1.0, score))


def _debounce(candidates: list[dict[str, Any]], gap_s: float = MERGE_GAP_S) -> list[dict[str, Any]]:
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda item: float(item["t"]))
    groups: list[list[dict[str, Any]]] = [[ordered[0]]]
    for item in ordered[1:]:
        if float(item["t"]) - float(groups[-1][-1]["t"]) < gap_s:
            groups[-1].append(item)
        else:
            groups.append([item])
    return [min(group, key=lambda item: float(item["ssim"])) for group in groups]


def _window(activity: list[dict[str, Any]], t: float, radius: float = 2.0) -> list[dict[str, Any]]:
    return [row for row in activity if abs(float(row["t"]) - t) <= radius]


def _suppressed(t: float, activity: list[dict[str, Any]], bbox_area: float) -> bool:
    if bbox_area < BBOX_MIN:
        return True
    window = [row for row in _window(activity, t) if abs(float(row["t"]) - t) > 0.05]
    if not window:
        window = _window(activity, t)
    if not window:
        return False
    noisy = sum(1 for row in window if row.get("cls") in SUPPRESS_CLASSES)
    return noisy / len(window) >= 0.5


def _stable_after(t: float, activity: list[dict[str, Any]]) -> bool:
    later = sorted(
        (row for row in activity if float(row["t"]) > t + 0.05),
        key=lambda row: float(row["t"]),
    )
    needed = [row for row in later if float(row["t"]) <= t + STABLE_S + 0.05]
    if len(needed) < 2:
        return False
    return all(float(row.get("ssim_prev") or 0.0) >= SSIM_STABLE for row in needed[:2])


def scene_cut_times(video_path) -> list[float]:
    """PySceneDetect ContentDetector(27) cut times, excluding the open at t=0."""
    try:
        from pipeline.slides.scenes import detect_scenes_pyscenedetect
    except ImportError:
        return []
    try:
        scenes = detect_scenes_pyscenedetect(video_path)
    except Exception:
        return []
    if not scenes or len(scenes) < 2:
        return []
    return [float(start) for start, _end in scenes[1:]]


def _nearest(activity: list[dict[str, Any]], t: float, tol: float = 1.0) -> Optional[dict[str, Any]]:
    best = None
    best_dist = tol
    for row in activity:
        dist = abs(float(row["t"]) - t)
        if dist <= best_dist:
            best = row
            best_dist = dist
    return best


def accept_transitions(
    activity: list[dict[str, Any]],
    scene_cuts: Optional[list[float]] = None,
) -> list[dict[str, Any]]:
    """Accepted cut times. SSIM must drop and the next two seconds must hold still."""
    candidates: list[dict[str, Any]] = []
    for row in activity:
        ssim = float(row.get("ssim_prev") or 1.0)
        if ssim < SSIM_CUT:
            candidates.append(
                {
                    "t": float(row["t"]),
                    "ssim": ssim,
                    "bbox_area": float(row.get("bbox_area") or 0.0),
                }
            )
    for cut in scene_cuts or []:
        row = _nearest(activity, float(cut), tol=1.0)
        if row is None:
            continue
        ssim = float(row.get("ssim_prev") or 1.0)
        if ssim < SSIM_CUT:
            candidates.append(
                {
                    "t": float(row["t"]),
                    "ssim": ssim,
                    "bbox_area": float(row.get("bbox_area") or 0.0),
                }
            )
    accepted = []
    for item in _debounce(candidates):
        t = float(item["t"])
        bbox = float(item["bbox_area"])
        if _suppressed(t, activity, bbox):
            continue
        if not _stable_after(t, activity):
            continue
        accepted.append({"t": round(t, 3), "ssim": round(float(item["ssim"]), 4), "bbox_area": round(bbox, 4)})
    return accepted


def transition_f1(
    predicted: list[float],
    truth: list[float],
    *,
    tolerance_s: float = 1.0,
) -> float:
    """One-to-one match within `tolerance_s`."""
    used: set[int] = set()
    tp = 0
    for guess in predicted:
        for index, target in enumerate(truth):
            if index in used:
                continue
            if abs(float(guess) - float(target)) <= tolerance_s:
                used.add(index)
                tp += 1
                break
    fp = len(predicted) - tp
    fn = len(truth) - tp
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2.0 * precision * recall / (precision + recall)
