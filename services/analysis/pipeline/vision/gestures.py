"""Category 12 gestures & body metrics (issue #40, SPEC §4.4.12).

Pure functions over pose-frame features and vision events. Distances are in
shoulder-width units. Metric ids and units match scoring.yaml v1.0.0.
No emotion labels, no face recognition, no demographic inference.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np

from pipeline.accessibility import (
    disabled_gesture_metrics,
    normalize_profile,
    video_metrics_opted_out,
)

# Heuristics (H) from SPEC §4.4.12.
ACTIVITY_TAU = 0.4  # shoulder widths / s
ACTIVITY_WINDOW_S = 1.0
HANDS_VIS_THRESH = 0.5
HANDS_GATE = 0.40  # issue AC / SPEC: hand-based metrics N/A below this
WEBCAM_CONF_CAP = 0.6
ADAPTOR_MIN_S = 0.5
SYNC_WINDOW_S = 0.300
LOCO_ALIGN_S = 5.0
SWAY_BAND_HZ = (0.2, 1.5)
GESTURE_SPACE_Y = (-1.7, -0.12)  # waist≈0 (down +); shoulders typically −1.3
GESTURE_SPACE_X = 0.25
SPACE_GRID_COLS = 8
SPACE_GRID_ROWS = 6
SPACE_GRID_X = (-1.6, 1.6)
SPACE_GRID_Y = (-2.0, 0.4)
CLASPED_X = 0.30
HIDDEN_WRIST_VIS = 0.5
ELBOW_VIS = 0.5

HAND_METRICS = (
    "gb_gesture_activity_ratio",
    "gb_gesture_space_ratio",
    "gb_self_adaptor_per_min",
    "gb_closed_posture_ratio",
    "gb_gesture_speech_sync",
)
UPPER_BODY_ONLY = ("gb_gesture_activity_ratio", "gb_self_adaptor_per_min")

UNITS = {
    "gb_gesture_activity_ratio": "ratio",
    "gb_gesture_space_ratio": "ratio",
    "gb_gesture_speech_sync": "ratio",
    "gb_self_adaptor_per_min": "per_minute",
    "gb_closed_posture_ratio": "ratio",
    "gb_sway_index": "shoulder_widths_sd",
    "gb_purposeful_movement": "ratio",
}


def _metric(
    metric_id: str,
    value: Optional[float],
    *,
    applicable: bool,
    confidence: float,
    failure_mode: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "value": None if value is None else round(float(value), 4),
        "unit": UNITS[metric_id],
        "basis": "heuristic",
        "source": "H",
        "confidence": round(float(confidence), 4),
        "applicable": bool(applicable and value is not None),
        "failure_mode": failure_mode,
    }


def _arr(rows: Sequence[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([row.get(key, float("nan")) for row in rows], dtype=np.float64)


def _times(rows: Sequence[dict[str, Any]]) -> np.ndarray:
    return np.asarray([float(row.get("t") or 0.0) for row in rows], dtype=np.float64)


def hands_visible_mask(rows: Sequence[dict[str, Any]], *, one_handed: bool) -> np.ndarray:
    """Share of frames with ≥1 wrist vis > 0.5 (SPEC). one_handed uses the same gate."""
    left = np.nan_to_num(_arr(rows, "wrist_l_vis"), nan=0.0)
    right = np.nan_to_num(_arr(rows, "wrist_r_vis"), nan=0.0)
    if one_handed:
        return (left > HANDS_VIS_THRESH) | (right > HANDS_VIS_THRESH)
    return (left > HANDS_VIS_THRESH) | (right > HANDS_VIS_THRESH)


def _wrist_speed(rows: Sequence[dict[str, Any]], *, one_handed: bool) -> np.ndarray:
    left = np.nan_to_num(_arr(rows, "wrist_speed_l"), nan=0.0)
    right = np.nan_to_num(_arr(rows, "wrist_speed_r"), nan=0.0)
    if not one_handed:
        return np.fmax(left, right)
    l_vis = np.nan_to_num(_arr(rows, "wrist_l_vis"), nan=0.0) > HANDS_VIS_THRESH
    r_vis = np.nan_to_num(_arr(rows, "wrist_r_vis"), nan=0.0) > HANDS_VIS_THRESH
    out = np.zeros(len(rows), dtype=np.float64)
    out[l_vis] = np.fmax(out[l_vis], left[l_vis])
    out[r_vis] = np.fmax(out[r_vis], right[r_vis])
    return out


def gb_gesture_activity_ratio(
    rows: Sequence[dict[str, Any]],
    *,
    tau: float = ACTIVITY_TAU,
    one_handed: bool = False,
) -> Optional[float]:
    """Share of 1-s windows whose max wrist speed exceeds τ_v (default 0.4 sw/s).

    Units: ratio. Source: heuristic (H). Failure: no speaking frames.
    """
    if not rows:
        return None
    times = _times(rows)
    speed = _wrist_speed(rows, one_handed=one_handed)
    t0 = float(times[0])
    t1 = float(times[-1])
    if t1 <= t0:
        return float(np.mean(speed > tau))
    hits = 0
    n = 0
    start = t0
    while start < t1 - 1e-9:
        end = start + ACTIVITY_WINDOW_S
        mask = (times >= start) & (times < end)
        if np.any(mask):
            n += 1
            if float(np.max(speed[mask])) > tau:
                hits += 1
        start = end
    if n == 0:
        return None
    return hits / n


def gb_gesture_space_ratio(
    rows: Sequence[dict[str, Any]],
    *,
    tau: float = ACTIVITY_TAU,
    one_handed: bool = False,
) -> Optional[float]:
    """Share of gesture frames with wrists between waist and shoulder, off midline.

    Units: ratio. Source: heuristic (H). Failure: no gesture frames.
    """
    if not rows:
        return None
    speed = _wrist_speed(rows, one_handed=one_handed)
    gesture = speed > tau
    if not np.any(gesture):
        return 0.0
    in_space = np.zeros(len(rows), dtype=bool)
    for i, row in enumerate(rows):
        if not gesture[i]:
            continue
        candidates = []
        for prefix in ("wrist_l", "wrist_r"):
            vis = float(row.get(f"{prefix}_vis") or 0.0)
            if vis <= HANDS_VIS_THRESH:
                continue
            x = row.get(f"{prefix}_x")
            y = row.get(f"{prefix}_y")
            if x is None or y is None or (isinstance(x, float) and np.isnan(x)):
                continue
            candidates.append(GESTURE_SPACE_Y[0] <= float(y) <= GESTURE_SPACE_Y[1] and abs(float(x)) >= GESTURE_SPACE_X)
        if one_handed:
            in_space[i] = any(candidates)
        else:
            in_space[i] = any(candidates)
    return float(np.mean(in_space[gesture]))


def wrist_space_density(
    rows: Sequence[dict[str, Any]],
    *,
    one_handed: bool = False,
) -> dict[str, Any]:
    """2-D wrist-position counts in shoulder-width units for the Body-tab silhouette.

    Missing wrists stay out of the grid. Counts are never invented.
    `one_handed` is accepted for the same call sites as other gesture helpers.
    """
    _ = one_handed
    cols, rows_n = SPACE_GRID_COLS, SPACE_GRID_ROWS
    x0, x1 = SPACE_GRID_X
    y0, y1 = SPACE_GRID_Y
    cells = [0] * (cols * rows_n)
    samples = 0
    for row in rows:
        for prefix in ("wrist_l", "wrist_r"):
            vis = float(row.get(f"{prefix}_vis") or 0.0)
            if vis <= HANDS_VIS_THRESH:
                continue
            x = row.get(f"{prefix}_x")
            y = row.get(f"{prefix}_y")
            if x is None or y is None:
                continue
            xf, yf = float(x), float(y)
            if isinstance(x, float) and np.isnan(xf):
                continue
            if xf < x0 or xf > x1 or yf < y0 or yf > y1:
                continue
            ci = min(cols - 1, max(0, int((xf - x0) / max(x1 - x0, 1e-6) * cols)))
            ri = min(rows_n - 1, max(0, int((yf - y0) / max(y1 - y0, 1e-6) * rows_n)))
            cells[ri * cols + ci] += 1
            samples += 1
    return {
        "cols": cols,
        "rows": rows_n,
        "x_min": x0,
        "x_max": x1,
        "y_min": y0,
        "y_max": y1,
        "samples": samples,
        "cells": cells,
    }


def gb_self_adaptor_per_min(
    events: Sequence[dict[str, Any]],
    duration_s: float,
) -> float:
    """Wrist-in-face/neck episodes ≥ 0.5 s, plus clasped repetitive motion, per minute.

    Units: per_minute. Source: heuristic (H).
    """
    count = 0
    for event in events:
        kind = event.get("type")
        if kind == "self_adaptor":
            if float(event.get("t_end") or 0) - float(event.get("t_start") or 0) >= ADAPTOR_MIN_S:
                count += 1
        elif kind == "clasped_fidget":
            count += 1
    return count * (60.0 / max(duration_s, 1.0))


def _clasped_fidget_events(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clasped hands with small repetitive motion (H)."""
    if len(rows) < 4:
        return []
    times = _times(rows)
    lx = _arr(rows, "wrist_l_x")
    rx = _arr(rows, "wrist_r_x")
    speed = np.fmax(
        np.nan_to_num(_arr(rows, "wrist_speed_l"), nan=0.0),
        np.nan_to_num(_arr(rows, "wrist_speed_r"), nan=0.0),
    )
    clasped = np.abs(np.nan_to_num(lx - rx, nan=99.0)) < CLASPED_X
    small = (speed > 0.02) & (speed < ACTIVITY_TAU)
    mask = clasped & small
    events: list[dict[str, Any]] = []
    start: Optional[int] = None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if float(times[i - 1] - times[start]) >= ADAPTOR_MIN_S:
                events.append(
                    {
                        "type": "clasped_fidget",
                        "t_start": float(times[start]),
                        "t_end": float(times[i - 1]),
                    }
                )
            start = None
    if start is not None and float(times[-1] - times[start]) >= ADAPTOR_MIN_S:
        events.append(
            {
                "type": "clasped_fidget",
                "t_start": float(times[start]),
                "t_end": float(times[-1]),
            }
        )
    return events


def gb_closed_posture_ratio(
    rows: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]],
    *,
    one_handed: bool = False,
) -> Optional[float]:
    """Share of time with crossed arms or hidden hands.

    Units: ratio. Source: heuristic (H). one_handed: a single hidden wrist is not closed.
    """
    if not rows:
        return None
    times = _times(rows)
    duration = max(float(times[-1] - times[0]), 1.0 / 15.0)
    closed = np.zeros(len(rows), dtype=bool)
    for i, row in enumerate(rows):
        if float(row.get("crossed_arms") or 0.0) >= 0.5:
            closed[i] = True
            continue
        l_vis = float(row.get("wrist_l_vis") or 0.0)
        r_vis = float(row.get("wrist_r_vis") or 0.0)
        el = float(row.get("elbow_l_vis") or 0.0)
        er = float(row.get("elbow_r_vis") or 0.0)
        elbows_ok = el > ELBOW_VIS or er > ELBOW_VIS
        if one_handed:
            hidden = l_vis <= HIDDEN_WRIST_VIS and r_vis <= HIDDEN_WRIST_VIS
        else:
            hidden = l_vis <= HIDDEN_WRIST_VIS and r_vis <= HIDDEN_WRIST_VIS
        if hidden and elbows_ok:
            closed[i] = True
    for event in events:
        if event.get("type") != "crossed_arms":
            continue
        t0 = float(event.get("t_start") or 0.0)
        t1 = float(event.get("t_end") or t0)
        closed |= (times >= t0) & (times <= t1)
    if duration <= 0:
        return None
    return float(np.mean(closed))


def gb_sway_index(
    rows: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]],
    *,
    fps: float = 15.0,
) -> Optional[float]:
    """Detrended SD of hip-mid x (shoulder widths) in 0.2–1.5 Hz, non-locomotion.

    Units: shoulder_widths_sd. Source: heuristic (H).
    Failure: hips not visible, or too little non-locomotion time.
    """
    if len(rows) < 8:
        return None
    times = _times(rows)
    hip = _arr(rows, "hip_mid_x")
    sw = np.nan_to_num(_arr(rows, "shoulder_width"), nan=0.0)
    hip_vis = np.nan_to_num(_arr(rows, "hip_visible"), nan=0.0)
    loco = np.zeros(len(rows), dtype=bool)
    for event in events:
        if event.get("type") != "locomotion":
            continue
        t0 = float(event.get("t_start") or 0.0)
        t1 = float(event.get("t_end") or t0)
        loco |= (times >= t0) & (times <= t1)
    keep = (~loco) & (hip_vis >= 0.5) & (sw > 1e-5) & np.isfinite(hip)
    if int(np.sum(keep)) < max(8, int(fps)):
        return None
    t = times[keep]
    x = (hip[keep] - float(np.mean(hip[keep]))) / np.maximum(sw[keep], 1e-6)
    A = np.column_stack([t - t[0], np.ones_like(t)])
    coef, *_ = np.linalg.lstsq(A, x, rcond=None)
    detrended = x - A @ coef
    filtered = _bandpass(detrended, fps)
    return float(np.std(filtered))


def _bandpass(signal: np.ndarray, fps: float) -> np.ndarray:
    if signal.size < 16 or fps <= 0:
        return signal
    try:
        from scipy.signal import butter, sosfiltfilt
    except Exception:
        return signal
    nyq = fps / 2.0
    lo, hi = SWAY_BAND_HZ
    if hi >= nyq * 0.95:
        return signal
    sos = butter(2, [lo / nyq, hi / nyq], btype="band", output="sos")
    try:
        return np.asarray(sosfiltfilt(sos, signal), dtype=np.float64)
    except Exception:
        return signal


def gb_purposeful_movement(
    events: Sequence[dict[str, Any]],
    section_boundaries_s: Optional[Sequence[float]],
) -> Optional[float]:
    """Share of locomotion segments within ±5 s of a section boundary.

    Units: ratio. Source: heuristic (H). N/A if no locomotion or no boundaries.
    """
    locos = [e for e in events if e.get("type") == "locomotion"]
    if not locos:
        return None
    if not section_boundaries_s:
        return None
    bounds = [float(b) for b in section_boundaries_s]
    hits = 0
    for event in locos:
        mid = 0.5 * (float(event.get("t_start") or 0.0) + float(event.get("t_end") or 0.0))
        if any(abs(mid - b) <= LOCO_ALIGN_S for b in bounds):
            hits += 1
    return hits / len(locos)


def gb_gesture_speech_sync(
    stroke_times_s: Sequence[float],
    prominence_times_s: Optional[Sequence[float]],
) -> Optional[float]:
    """Share of gesture-stroke peaks within ±300 ms of a prosodic prominence.

    Units: ratio. Source: heuristic (H). Experimental; scoring.yaml weight 0.
    Failure: no strokes or no prominences → N/A, never invented.
    """
    if not stroke_times_s or not prominence_times_s:
        return None
    prom = np.asarray(list(prominence_times_s), dtype=np.float64)
    hits = 0
    for t in stroke_times_s:
        if float(np.min(np.abs(prom - float(t)))) <= SYNC_WINDOW_S:
            hits += 1
    return hits / len(stroke_times_s)


def _stroke_times(events: Sequence[dict[str, Any]]) -> list[float]:
    return [float(e["t_start"]) for e in events if e.get("type") == "gesture_stroke"]


def _locomotion_segments(events: Sequence[dict[str, Any]]) -> list[dict[str, float]]:
    out = []
    for event in events:
        if event.get("type") != "locomotion":
            continue
        out.append(
            {
                "t_start": float(event.get("t_start") or 0.0),
                "t_end": float(event.get("t_end") or 0.0),
            }
        )
    return out


def compute_gesture_metrics(
    pose_rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    duration_s: float,
    accessibility: Optional[dict[str, Any]] = None,
    webcam_framing: bool = False,
    audio_only: bool = False,
    prominence_times_s: Optional[Sequence[float]] = None,
    section_boundaries_s: Optional[Sequence[float]] = None,
    fps: float = 15.0,
) -> Optional[dict[str, Any]]:
    """Return scoring-config v1.0.0 gestures_body values, or None if N/A."""
    profile = normalize_profile(accessibility)
    if audio_only or video_metrics_opted_out(profile):
        return None
    visible = [row for row in pose_rows if row.get("person_visible", 1.0)]
    if not visible:
        return None
    one_handed = bool(profile["one_handed"])
    hands_mask = hands_visible_mask(visible, one_handed=one_handed)
    hands_ratio = float(np.mean(hands_mask)) if hands_mask.size else 0.0
    person_ratio = len(visible) / max(len(pose_rows), 1)
    extra_events = list(events) + _clasped_fidget_events(visible)
    stroke_times = _stroke_times(extra_events)
    conf = 0.75
    if webcam_framing:
        conf = min(conf, WEBCAM_CONF_CAP)
    hip_ratio = float(np.mean(np.nan_to_num(_arr(visible, "hip_visible"), nan=0.0) >= 0.5))
    if hip_ratio < 0.3:
        webcam_framing = True
        conf = min(conf, WEBCAM_CONF_CAP)

    activity = gb_gesture_activity_ratio(visible, one_handed=one_handed)
    activity_windows: list[dict[str, float]] = []
    times = _times(visible)
    speed = _wrist_speed(visible, one_handed=one_handed)
    if times.size:
        w0 = float(times[0])
        w1 = float(times[-1])
        start = w0
        while start < w1 - 1e-9:
            end = start + ACTIVITY_WINDOW_S
            mask = (times >= start) & (times < end)
            if np.any(mask):
                activity_windows.append(
                    {"start": round(start, 3), "value": round(float(np.max(speed[mask])), 4)}
                )
            start = end
    space = gb_gesture_space_ratio(visible, one_handed=one_handed)
    adaptor = gb_self_adaptor_per_min(extra_events, max(duration_s, 1.0))
    closed = gb_closed_posture_ratio(visible, extra_events, one_handed=one_handed)
    sway = gb_sway_index(visible, extra_events, fps=fps)
    purposeful = gb_purposeful_movement(extra_events, section_boundaries_s)
    sync = gb_gesture_speech_sync(stroke_times, prominence_times_s)

    metrics = {
        "gb_gesture_activity_ratio": _metric("gb_gesture_activity_ratio", activity, applicable=True, confidence=conf),
        "gb_gesture_space_ratio": _metric("gb_gesture_space_ratio", space, applicable=True, confidence=conf),
        "gb_gesture_speech_sync": _metric(
            "gb_gesture_speech_sync",
            sync,
            applicable=sync is not None,
            confidence=min(conf, 0.55),
            failure_mode=None if sync is not None else "no_prominence_or_strokes",
        ),
        "gb_self_adaptor_per_min": _metric("gb_self_adaptor_per_min", adaptor, applicable=True, confidence=conf),
        "gb_closed_posture_ratio": _metric("gb_closed_posture_ratio", closed, applicable=True, confidence=conf),
        "gb_sway_index": _metric(
            "gb_sway_index",
            sway,
            applicable=sway is not None and not webcam_framing,
            confidence=conf,
            failure_mode="webcam_or_hips_unavailable" if sway is None or webcam_framing else None,
        ),
        "gb_purposeful_movement": _metric(
            "gb_purposeful_movement",
            purposeful,
            applicable=purposeful is not None and not webcam_framing,
            confidence=conf,
            failure_mode="no_locomotion_or_boundaries" if purposeful is None else None,
        ),
    }

    if hands_ratio < HANDS_GATE:
        for metric_id in HAND_METRICS:
            metrics[metric_id]["applicable"] = False
            metrics[metric_id]["value"] = None
            metrics[metric_id]["failure_mode"] = "hands_visible_below_40pct"

    if webcam_framing:
        for metric_id, row in metrics.items():
            if metric_id not in UPPER_BODY_ONLY:
                if metric_id in {"gb_sway_index", "gb_purposeful_movement", "gb_gesture_space_ratio", "gb_closed_posture_ratio"}:
                    row["applicable"] = False
                    if metric_id != "gb_gesture_speech_sync":
                        row["value"] = None
                    row["failure_mode"] = row.get("failure_mode") or "webcam_upper_body_only"
            row["confidence"] = min(float(row["confidence"]), WEBCAM_CONF_CAP)

    disabled = disabled_gesture_metrics(profile)
    for metric_id in disabled:
        if metric_id in metrics:
            metrics[metric_id]["applicable"] = False
            metrics[metric_id]["value"] = None
            metrics[metric_id]["failure_mode"] = "accessibility_profile"

    payload = {
        "person_visible_ratio": round(person_ratio, 4),
        "hands_visible_ratio": round(hands_ratio, 4),
        "webcam_framing": bool(webcam_framing),
        "audio_only": False,
        "accessibility": profile,
        "disabled_metrics": sorted(disabled),
        "stroke_times_s": [round(t, 3) for t in stroke_times],
        "locomotion_segments": _locomotion_segments(extra_events),
        "activity_windows": activity_windows,
        "space_density": wrist_space_density(visible, one_handed=one_handed),
        "metrics": metrics,
    }
    return payload


def attach_late_inputs(
    payload: dict[str, Any],
    *,
    prominence_times_s: Optional[Sequence[float]] = None,
    section_boundaries_s: Optional[Sequence[float]] = None,
    accessibility: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Fill speech-sync and purposeful-movement once ASR/content exist. Never invents."""
    metrics = payload.setdefault("metrics", {})
    profile = normalize_profile(accessibility if accessibility is not None else payload.get("accessibility"))
    disabled = disabled_gesture_metrics(profile)
    webcam = bool(payload.get("webcam_framing"))
    hands_ratio = float(payload.get("hands_visible_ratio") or 0.0)
    conf = WEBCAM_CONF_CAP if webcam else 0.75

    if "gb_gesture_speech_sync" in metrics:
        if hands_ratio < HANDS_GATE or "gb_gesture_speech_sync" in disabled:
            metrics["gb_gesture_speech_sync"] = _metric(
                "gb_gesture_speech_sync",
                None,
                applicable=False,
                confidence=conf,
                failure_mode="hands_visible_below_40pct" if hands_ratio < HANDS_GATE else "accessibility_profile",
            )
        else:
            sync = gb_gesture_speech_sync(payload.get("stroke_times_s") or [], prominence_times_s)
            metrics["gb_gesture_speech_sync"] = _metric(
                "gb_gesture_speech_sync",
                sync,
                applicable=sync is not None,
                confidence=min(conf, 0.55),
                failure_mode=None if sync is not None else "no_prominence_or_strokes",
            )

    if "gb_purposeful_movement" in metrics:
        if webcam or "gb_purposeful_movement" in disabled:
            metrics["gb_purposeful_movement"] = _metric(
                "gb_purposeful_movement",
                None,
                applicable=False,
                confidence=conf,
                failure_mode="accessibility_profile" if "gb_purposeful_movement" in disabled else "webcam_upper_body_only",
            )
        else:
            events = [
                {"type": "locomotion", **seg} for seg in (payload.get("locomotion_segments") or [])
            ]
            purposeful = gb_purposeful_movement(events, section_boundaries_s)
            metrics["gb_purposeful_movement"] = _metric(
                "gb_purposeful_movement",
                purposeful,
                applicable=purposeful is not None,
                confidence=conf,
                failure_mode=None if purposeful is not None else "no_locomotion_or_boundaries",
            )
    payload["accessibility"] = profile
    payload["disabled_metrics"] = sorted(disabled)
    return payload
