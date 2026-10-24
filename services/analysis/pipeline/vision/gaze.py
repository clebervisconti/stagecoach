"""Category 13 eye-contact proxies from head orientation (issue #41, SPEC §4.4.13).

This is not eye contact. Labels are audience-facing time (head orientation)
or gaze-to-camera (head pose + eyeLook blendshapes). L2CS-Net is not used
(pretrained-weight training-data terms not re-checked; ADR-029).
No emotion inference, face recognition, or demographic labels.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Sequence

import numpy as np

from pipeline.accessibility import normalize_profile, video_metrics_opted_out
from pipeline.vision.features import EYE_LOOK

# Heuristics (H) from SPEC §4.4.13.
TO_CAMERA_YAW = 15.0
TO_CAMERA_PITCH = 12.0
TO_CAMERA_GAZE = 10.0
STAGE_YAW = 35.0
STAGE_PITCH_MIN = -15.0
NOTES_PITCH = -20.0
HOLD_MIN_S = 2.0
YAW_BIN_DEG = 10.0
FACE_PX_FULL = 60.0
FACE_VISIBLE_FULL = 0.60
WIDE_SHOT_CONF = 0.6
GAZE_SCALE_DEG = 30.0  # blendshape score 1.0 ≈ 30° (H)
# Online modes score gaze only while the camera fills the frame (SPEC §9.5).
# Below this share of the talk, the category stays N/A instead of a low score.
LOW_CAMERA_COVERAGE = 0.20
MID_CAMERA_COVERAGE = 0.50
ONLINE_GAZE_MODES = frozenset({"webinar", "online_talk", "recorded_video"})
CAMERA_COVERAGE_REASON = (
    "The camera fills the frame for too little of this recording to score where you look."
)

UNITS = {
    "ec_audience_facing_ratio": "ratio",
    "ec_gaze_distribution_evenness": "entropy",
    "ec_gaze_holds_per_min": "per_minute",
    "ec_reading_head_down_ratio": "ratio",
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


def eye_gaze_deg(blendshapes: Optional[dict[str, Any]]) -> tuple[Optional[float], Optional[float]]:
    """Approximate gaze yaw/pitch in degrees from MediaPipe eyeLook* scores (H).

    Not L2CS-Net. Missing blendshapes → (None, None) so the head-pose gate
    still runs without inventing eye direction.
    """
    if not blendshapes:
        return None, None
    if not any(k in blendshapes for k in EYE_LOOK):
        return None, None
    h = (
        float(blendshapes.get("eyeLookOutLeft") or 0.0)
        - float(blendshapes.get("eyeLookInLeft") or 0.0)
        + float(blendshapes.get("eyeLookInRight") or 0.0)
        - float(blendshapes.get("eyeLookOutRight") or 0.0)
    ) / 2.0
    v = (
        float(blendshapes.get("eyeLookDownLeft") or 0.0)
        + float(blendshapes.get("eyeLookDownRight") or 0.0)
        - float(blendshapes.get("eyeLookUpLeft") or 0.0)
        - float(blendshapes.get("eyeLookUpRight") or 0.0)
    ) / 2.0
    return h * GAZE_SCALE_DEG, v * GAZE_SCALE_DEG


def is_to_camera_setup(setup: str) -> bool:
    return setup == "to_camera"


def audience_facing_mask(
    face_rows: Sequence[dict[str, Any]],
    *,
    setup: str,
    use_eye_gaze: bool,
) -> np.ndarray:
    """Per-row facing proxy. To-camera vs stage thresholds from SPEC §4.4.13 (H)."""
    to_camera = is_to_camera_setup(setup)
    out = np.zeros(len(face_rows), dtype=bool)
    for i, row in enumerate(face_rows):
        if not row.get("face_visible"):
            continue
        yaw = row.get("yaw_deg")
        pitch = row.get("pitch_deg")
        if yaw is None or pitch is None or (isinstance(yaw, float) and math.isnan(yaw)):
            continue
        yaw_f = float(yaw)
        pitch_f = float(pitch)
        if to_camera:
            ok = abs(yaw_f) <= TO_CAMERA_YAW and abs(pitch_f) <= TO_CAMERA_PITCH
            if use_eye_gaze:
                gx, gy = eye_gaze_deg(row.get("blendshapes") or {})
                if gx is None or gy is None:
                    continue
                ok = ok and abs(gx) <= TO_CAMERA_GAZE and abs(gy) <= TO_CAMERA_GAZE
        else:
            ok = abs(yaw_f) <= STAGE_YAW and pitch_f >= STAGE_PITCH_MIN
        out[i] = bool(ok)
    return out


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


def yaw_histogram_entropy(yaws: Sequence[float], *, lo: float, hi: float, bin_deg: float) -> Optional[float]:
    """Normalized entropy of yaw in `bin_deg` bins inside [lo, hi]. Units: entropy."""
    if hi <= lo or bin_deg <= 0:
        return None
    clipped = [y for y in yaws if lo <= y <= hi]
    if len(clipped) < 4:
        return None
    n_bins = max(int(round((hi - lo) / bin_deg)), 1)
    hist, _ = np.histogram(clipped, bins=n_bins, range=(lo, hi))
    total = float(hist.sum())
    if total <= 0:
        return None
    p = hist[hist > 0] / total
    h = float(-np.sum(p * np.log(p)))
    return h / math.log(n_bins) if n_bins > 1 else 0.0


def yaw_histogram_bins(
    yaws: Sequence[float], *, lo: float, hi: float, bin_deg: float
) -> list[dict[str, float]]:
    """Count bins for the Body-tab yaw histogram. Empty when there are no yaw samples."""
    if hi <= lo or bin_deg <= 0:
        return []
    clipped = [float(y) for y in yaws if lo <= y <= hi]
    if not clipped:
        return []
    n_bins = max(int(round((hi - lo) / bin_deg)), 1)
    hist, edges = np.histogram(clipped, bins=n_bins, range=(lo, hi))
    out: list[dict[str, float]] = []
    for count, left, right in zip(hist, edges[:-1], edges[1:]):
        out.append(
            {
                "center": round(float((left + right) / 2.0), 2),
                "lo": round(float(left), 2),
                "hi": round(float(right), 2),
                "count": int(count),
            }
        )
    return out


def camera_lens_windows(layout: Optional[dict[str, Any]]) -> Optional[list[tuple[float, float]]]:
    """Times when gaze toward the lens is the right measurement.

    SPEC §9.5: while a screen is shared, only camera-full segments count,
    because looking at the shared screen is expected. Returns None when the
    layout has no segments, so stage and unreviewed files keep the old path.
    """
    if not layout or not layout.get("segments"):
        return None
    windows: list[tuple[float, float]] = []
    for segment in layout.get("segments") or []:
        regions = segment.get("regions") or []
        has_camera = any(region.get("role") == "camera" for region in regions)
        has_screen = any(region.get("role") == "screen" for region in regions)
        kind = str(segment.get("kind") or "")
        if kind != "camera_full" and not (has_camera and not has_screen):
            continue
        start = float(segment.get("t_start") or 0.0)
        end = segment.get("t_end")
        if end is None:
            continue
        stop = float(end)
        if stop > start:
            windows.append((start, stop))
    return windows


def _covers(t: float, windows: Sequence[tuple[float, float]]) -> bool:
    return any(start <= t <= stop for start, stop in windows)


def _gaze_not_applicable(reason: str, coverage: float) -> dict[str, Any]:
    metrics = {
        metric_id: _metric(metric_id, None, applicable=False, confidence=0.0, failure_mode="camera_coverage_low")
        for metric_id in UNITS
    }
    return {
        "proxy_label": "audience-facing time (head orientation)",
        "eye_contact": False,
        "l2cs_net": False,
        "applicable": False,
        "na_reason": reason,
        "camera_coverage_ratio": round(coverage, 4),
        "setup": "to_camera",
        "use_eye_gaze": False,
        "wide_shot": False,
        "face_visible_ratio": 0.0,
        "face_px_median": 0.0,
        "hold_count": 0,
        "yaw_histogram": [],
        "metrics": metrics,
    }


def compute_gaze_metrics(
    face_rows: list[dict[str, Any]],
    *,
    duration_s: float,
    setup: str = "unknown",
    accessibility: Optional[dict[str, Any]] = None,
    audio_only: bool = False,
    mean_face_height_px: Optional[float] = None,
    delivery_mode: str = "stage",
    layout: Optional[dict[str, Any]] = None,
    time_origin_s: float = 0.0,
    session_duration_s: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """Return scoring-config v1.0.0 eye_contact values, or None if N/A."""
    profile = normalize_profile(accessibility)
    if audio_only or video_metrics_opted_out(profile):
        return None
    if not face_rows:
        return None
    coverage_cap: Optional[float] = None
    if delivery_mode in ONLINE_GAZE_MODES:
        windows = camera_lens_windows(layout)
        if windows is not None:
            covered = sum(stop - start for start, stop in windows)
            talk_s = session_duration_s
            if talk_s is None:
                ends = [stop for _, stop in windows]
                talk_s = max(duration_s + max(0.0, time_origin_s), max(ends, default=0.0), 1.0)
            coverage = covered / max(float(talk_s), 1.0)
            if coverage < LOW_CAMERA_COVERAGE or not windows:
                return _gaze_not_applicable(CAMERA_COVERAGE_REASON, coverage)
            origin = float(time_origin_s or 0.0)
            face_rows = [
                row for row in face_rows if _covers(float(row.get("t") or 0.0) + origin, windows)
            ]
            if not face_rows:
                return _gaze_not_applicable(CAMERA_COVERAGE_REASON, coverage)
            if coverage < MID_CAMERA_COVERAGE:
                coverage_cap = 0.55
    visible = [row for row in face_rows if row.get("face_visible")]
    face_ratio = len(visible) / max(len(face_rows), 1)
    heights = [float(row.get("face_height_px") or 0.0) for row in visible]
    face_px = float(np.median(heights)) if heights else float(mean_face_height_px or 0.0)
    if mean_face_height_px is not None and face_px <= 0:
        face_px = float(mean_face_height_px)

    setup_norm = setup if setup in {"stage", "to_camera", "screen_recording", "unknown"} else "unknown"
    if setup_norm == "screen_recording":
        return None
    if setup_norm == "unknown":
        setup_norm = "to_camera" if face_px >= 80 else "stage"

    wide_shot = face_px < FACE_PX_FULL or (setup_norm == "stage" and face_px < 80)
    use_eye_gaze = is_to_camera_setup(setup_norm) and not wide_shot and face_px >= FACE_PX_FULL
    conf = 0.75
    if wide_shot or face_ratio < FACE_VISIBLE_FULL:
        conf = min(conf, WIDE_SHOT_CONF)
    if coverage_cap is not None:
        conf = min(conf, coverage_cap)

    facing = audience_facing_mask(visible if visible else face_rows, setup=setup_norm, use_eye_gaze=use_eye_gaze)
    # Ratio over speaking/visible face frames (gate), not invented zeros for missing faces.
    if not visible:
        return None
    facing_ratio = float(np.mean(facing)) if facing.size else 0.0
    times = np.asarray([float(row.get("t") or 0.0) for row in visible], dtype=np.float64)
    holds = _episodes(times, facing, HOLD_MIN_S)
    holds_per_min = len(holds) * (60.0 / max(duration_s, 1.0))

    down = np.asarray(
        [
            (row.get("pitch_deg") is not None)
            and not (isinstance(row.get("pitch_deg"), float) and math.isnan(row.get("pitch_deg")))
            and float(row.get("pitch_deg")) < NOTES_PITCH
            for row in visible
        ],
        dtype=bool,
    )
    reading_ratio = float(np.mean(down)) if down.size else 0.0

    evenness: Optional[float] = None
    evenness_applicable = setup_norm == "stage"
    all_yaws = [
        float(row["yaw_deg"])
        for row in visible
        if row.get("yaw_deg") is not None
        and not (isinstance(row.get("yaw_deg"), float) and math.isnan(row.get("yaw_deg")))
    ]
    yaw_bins = yaw_histogram_bins(all_yaws, lo=-STAGE_YAW, hi=STAGE_YAW, bin_deg=YAW_BIN_DEG)
    if evenness_applicable:
        facing_yaws = [
            float(row["yaw_deg"])
            for row, flag in zip(visible, facing)
            if flag
            and row.get("yaw_deg") is not None
            and not (isinstance(row.get("yaw_deg"), float) and math.isnan(row.get("yaw_deg")))
        ]
        evenness = yaw_histogram_entropy(
            facing_yaws, lo=-STAGE_YAW, hi=STAGE_YAW, bin_deg=YAW_BIN_DEG
        )

    metrics = {
        "ec_audience_facing_ratio": _metric(
            "ec_audience_facing_ratio", facing_ratio, applicable=True, confidence=conf
        ),
        "ec_gaze_distribution_evenness": _metric(
            "ec_gaze_distribution_evenness",
            evenness,
            applicable=evenness_applicable and evenness is not None,
            confidence=conf,
            failure_mode=None if evenness is not None else ("to_camera_na" if not evenness_applicable else "too_few_yaw_samples"),
        ),
        "ec_gaze_holds_per_min": _metric(
            "ec_gaze_holds_per_min", holds_per_min, applicable=True, confidence=conf
        ),
        "ec_reading_head_down_ratio": _metric(
            "ec_reading_head_down_ratio", reading_ratio, applicable=True, confidence=conf
        ),
    }

    return {
        "proxy_label": "audience-facing time (head orientation)",
        "eye_contact": False,
        "l2cs_net": False,
        "setup": setup_norm,
        "use_eye_gaze": bool(use_eye_gaze),
        "wide_shot": bool(wide_shot),
        "face_visible_ratio": round(face_ratio, 4),
        "face_px_median": round(face_px, 2),
        "hold_count": len(holds),
        "yaw_histogram": yaw_bins,
        "metrics": metrics,
    }
