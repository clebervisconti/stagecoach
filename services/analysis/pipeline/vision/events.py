"""Vision events from per-frame pose/face features (issue #39, SPEC §6.5 step 5).

Types: gesture_stroke, self_adaptor, crossed_arms, notes_down, screen_turn,
locomotion, smile, flat_face. Smile and flat_face require expression_analysis.
No emotion labels.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from pipeline.vision.features import BLENDSHAPE_SUBSET

# Heuristics (H) from SPEC §4.4.12–14 and §6.5.
STROKE_SPEED = 0.4  # shoulder widths / s
ADAPTOR_DIST = 0.45
ADAPTOR_MIN_S = 0.5
CROSSED_MIN_S = 0.4
NOTES_PITCH = -20.0
NOTES_MIN_S = 2.0
SCREEN_YAW = 50.0
SCREEN_MIN_S = 0.4
LOCO_DISP = 0.5  # shoulder widths
LOCO_WINDOW_S = 2.0
SMILE_THRESH = 0.4
FLAT_WINDOW_S = 60.0
FLAT_PERCENTILE = 15.0


def _episodes(times: np.ndarray, mask: np.ndarray, min_s: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    start: Optional[int] = None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if float(times[i - 1] - times[start]) >= min_s:
                out.append((float(times[start]), float(times[i - 1])))
            start = None
    if start is not None and float(times[-1] - times[start]) >= min_s:
        out.append((float(times[start]), float(times[-1])))
    return out


def _event(kind: str, t0: float, t1: float, **extra: Any) -> dict[str, Any]:
    row = {
        "type": kind,
        "t_start": round(t0, 3),
        "t_end": round(max(t1, t0), 3),
        "source": "heuristic",
    }
    row.update(extra)
    return row


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([row.get(key, float("nan")) for row in rows], dtype=np.float64)


def detect_events(
    pose_rows: list[dict[str, Any]],
    face_rows: list[dict[str, Any]],
    *,
    expression_metrics: bool,
    threshold_scale: float = 1.0,
) -> list[dict[str, Any]]:
    """Return timestamped events. Empty if there is no person."""
    events: list[dict[str, Any]] = []
    if not pose_rows:
        return events
    scale = max(float(threshold_scale), 0.25)
    times = _series(pose_rows, "t")

    speed = np.fmax(
        np.nan_to_num(_series(pose_rows, "wrist_speed_l"), nan=0.0),
        np.nan_to_num(_series(pose_rows, "wrist_speed_r"), nan=0.0),
    )
    tau = STROKE_SPEED * scale
    for i in range(1, len(speed) - 1):
        if speed[i] >= tau and speed[i] >= speed[i - 1] and speed[i] >= speed[i + 1]:
            t = float(times[i])
            events.append(_event("gesture_stroke", t, t, peak_speed=round(float(speed[i]), 3)))

    adaptor = np.nan_to_num(_series(pose_rows, "hand_face_dist"), nan=99.0) < (ADAPTOR_DIST * scale)
    for t0, t1 in _episodes(times, adaptor, ADAPTOR_MIN_S):
        events.append(_event("self_adaptor", t0, t1))

    crossed = np.nan_to_num(_series(pose_rows, "crossed_arms"), nan=0.0) >= 0.5
    for t0, t1 in _episodes(times, crossed, CROSSED_MIN_S):
        events.append(_event("crossed_arms", t0, t1))

    hip = np.column_stack([_series(pose_rows, "hip_mid_x"), _series(pose_rows, "hip_mid_y")])
    sw = np.nan_to_num(_series(pose_rows, "shoulder_width"), nan=1e-6)
    loco = np.zeros(len(times), dtype=bool)
    for i, t in enumerate(times):
        j = i
        while j < len(times) and times[j] < t + LOCO_WINDOW_S:
            j += 1
        if j <= i:
            continue
        disp = float(np.linalg.norm(hip[j - 1] - hip[i])) / max(float(sw[i]), 1e-6)
        if disp > LOCO_DISP * scale:
            loco[i : j] = True
    for t0, t1 in _episodes(times, loco, 0.3):
        events.append(_event("locomotion", t0, t1))

    if face_rows:
        ft = _series(face_rows, "t")
        pitch = _series(face_rows, "pitch_deg")
        yaw = _series(face_rows, "yaw_deg")
        notes = np.nan_to_num(pitch, nan=0.0) < (NOTES_PITCH / scale if scale else NOTES_PITCH)
        for t0, t1 in _episodes(ft, notes, NOTES_MIN_S):
            events.append(_event("notes_down", t0, t1))
        turns = np.abs(np.nan_to_num(yaw, nan=0.0)) > (SCREEN_YAW * scale)
        for t0, t1 in _episodes(ft, turns, SCREEN_MIN_S):
            events.append(_event("screen_turn", t0, t1))

        if expression_metrics:
            smiles = []
            express = []
            for row in face_rows:
                b = row.get("blendshapes") or {}
                sm = (float(b.get("mouthSmileLeft", 0.0)) + float(b.get("mouthSmileRight", 0.0))) / 2.0
                smiles.append(sm)
                subset = [float(b.get(name, 0.0)) for name in BLENDSHAPE_SUBSET]
                express.append(float(np.std(subset)) if subset else 0.0)
            smile_mask = np.asarray(smiles) > SMILE_THRESH
            for t0, t1 in _episodes(ft, smile_mask, 0.2):
                events.append(_event("smile", t0, t1))
            expr = np.asarray(express, dtype=np.float64)
            if expr.size and float(ft[-1] - ft[0]) >= FLAT_WINDOW_S:
                cutoff = float(np.percentile(expr, FLAT_PERCENTILE))
                flat = expr <= cutoff
                for t0, t1 in _episodes(ft, flat, FLAT_WINDOW_S):
                    events.append(_event("flat_face", t0, t1, expressivity=round(cutoff, 4)))

    events.sort(key=lambda e: (e["t_start"], e["type"]))
    return events
