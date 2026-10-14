"""Category 15 Energy & Presence fusion (issue #45, SPEC §4.4.15).

Composite E(t) is the mean of z-scores of whichever of loudness, PVQ,
gesture activity, and expressivity are available. Not confidence detection.
No SER and no emotion labels. Missing modalities are omitted, never invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

BIN_S = 60.0  # SPEC: E(t) per minute (H)
SOFT_BELOW_DB = 12.0  # H, SPEC §4.4.15
MIN_BINS_FOR_THIRDS = 3
UNITS = {
    "ep_too_soft_ratio": "ratio",
    "ep_energy_trajectory": "z_score_delta",
    "ep_key_moment_lift": "z_score",
    "ep_confident_language": "llm_level",
    "ep_recovery": "llm_level",
}


def _finite(values: Sequence[Any]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=np.float64)
    return arr[np.isfinite(arr)]


def too_soft_ratio(
    intensity_db: Sequence[float],
    *,
    below_db: float = SOFT_BELOW_DB,
) -> float | None:
    """Share of samples more than `below_db` below the median loudness (H)."""
    arr = _finite(intensity_db)
    if arr.size == 0:
        return None
    median = float(np.median(arr))
    return float(np.mean(arr < (median - below_db)))


def _points_to_bins(
    points: Sequence[dict[str, Any]],
    duration_s: float,
    *,
    bin_s: float = BIN_S,
) -> list[float | None]:
    n = max(1, int(np.ceil(max(duration_s, 1e-6) / bin_s)))
    buckets: list[list[float]] = [[] for _ in range(n)]
    for point in points:
        if not isinstance(point, dict):
            continue
        value = point.get("value")
        if value is None:
            continue
        try:
            t = float(
                point.get("start")
                if point.get("start") is not None
                else point.get("t") or 0.0
            )
            v = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(v):
            continue
        idx = min(n - 1, max(0, int(t // bin_s)))
        buckets[idx].append(v)
    return [float(np.mean(b)) if b else None for b in buckets]


def _zscore(bins: Sequence[float | None]) -> list[float | None]:
    vals = [v for v in bins if v is not None]
    if not vals:
        return [None] * len(bins)
    arr = np.asarray(vals, dtype=np.float64)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=0))
    out: list[float | None] = []
    for v in bins:
        if v is None:
            out.append(None)
        elif std < 1e-9:
            out.append(0.0)
        else:
            out.append((float(v) - mean) / std)
    return out


def composite_energy(
    modalities: dict[str, Sequence[dict[str, Any]]],
    duration_s: float,
    *,
    bin_s: float = BIN_S,
) -> list[dict[str, Any]]:
    """Per-minute E(t) = mean of available modality z-scores. Empty dict → []."""
    z_rows: list[list[float | None]] = []
    n = max(1, int(np.ceil(max(duration_s, 1e-6) / bin_s)))
    for points in modalities.values():
        if not points:
            continue
        bins = _points_to_bins(points, duration_s, bin_s=bin_s)
        if all(v is None for v in bins):
            continue
        z_rows.append(_zscore(bins))
    if not z_rows:
        return []
    out: list[dict[str, Any]] = []
    for i in range(n):
        vals = [row[i] for row in z_rows if row[i] is not None]
        if not vals:
            continue
        out.append(
            {
                "t": round(i * bin_s, 3),
                "value": float(np.mean(vals)),
                "n_modalities": len(vals),
            }
        )
    return out


def energy_trajectory(
    series: Sequence[dict[str, Any]], duration_s: float
) -> float | None:
    """E(last third) − E(first third). None if either third is empty."""
    if duration_s <= 0 or not series:
        return None
    first_end = duration_s / 3.0
    last_start = 2.0 * duration_s / 3.0
    first = [
        float(p["value"])
        for p in series
        if float(p.get("t") or 0) < first_end and p.get("value") is not None
    ]
    last = [
        float(p["value"])
        for p in series
        if float(p.get("t") or 0) >= last_start and p.get("value") is not None
    ]
    if len(series) < MIN_BINS_FOR_THIRDS or not first or not last:
        return None
    return float(np.mean(last) - np.mean(first))


def key_moment_lift(
    series: Sequence[dict[str, Any]],
    key_times_s: Sequence[float],
    *,
    window_s: float = BIN_S,
) -> float | None:
    """Mean E in minute-bins that contain a key moment minus mean E elsewhere."""
    if not series or not key_times_s:
        return None
    keys = [float(t) for t in key_times_s if np.isfinite(t)]
    if not keys:
        return None
    key_bins = {int(t // window_s) for t in keys}
    at: list[float] = []
    elsewhere: list[float] = []
    for point in series:
        value = point.get("value")
        if value is None:
            continue
        t = float(point.get("t") or 0.0)
        if int(t // window_s) in key_bins:
            at.append(float(value))
        else:
            elsewhere.append(float(value))
    if not at or not elsewhere:
        return None
    return float(np.mean(at) - np.mean(elsewhere))


def _seg_times(transcript: dict[str, Any] | None, seg_id: str | None) -> float | None:
    if not seg_id or not transcript:
        return None
    try:
        text = str(seg_id)
        index = int(text[1:]) - 1 if text[:1].upper() == "S" else int(text)
    except (TypeError, ValueError):
        return None
    segments = transcript.get("segments") or []
    if 0 <= index < len(segments):
        return float(segments[index].get("start") or 0.0)
    return None


def key_moment_times(
    content: dict[str, Any] | None, transcript: dict[str, Any] | None
) -> list[float]:
    """LLM-marked core message, story close, CTA, memorable moment — timestamps only."""
    if not content:
        return []
    times: list[float] = []
    message = content.get("message") or {}
    core = message.get("core_message") or {}
    for seg in core.get("seg_ids") or []:
        t = _seg_times(transcript, seg)
        if t is not None:
            times.append(t)
    cta = message.get("cta") or {}
    cta_segs = list(cta.get("seg_ids") or [])
    if cta.get("seg_id"):
        cta_segs.append(cta["seg_id"])
    for seg in cta_segs:
        t = _seg_times(transcript, seg)
        if t is not None:
            times.append(t)
    story = content.get("story_impact") or {}
    for item in story.get("stories") or []:
        t = _seg_times(transcript, item.get("end_seg") or item.get("start_seg"))
        if t is not None:
            times.append(t)
    memorable = story.get("memorable_moment") or {}
    t = _seg_times(transcript, memorable.get("seg_id"))
    if t is not None:
        times.append(t)
    return times


def disruption_count(
    pauses: dict[str, Any] | None, content: dict[str, Any] | None
) -> int:
    """Long pauses or LLM-noted disruptions. Zero → recovery is N/A."""
    n = 0
    energy = (content or {}).get("energy") or {}
    if energy.get("disruptions"):
        n += int(energy.get("disruption_count") or 1)
    for pause in (pauses or {}).get("pauses") or []:
        kind = str(pause.get("kind") or "")
        dur = float(pause.get("duration") or 0.0)
        if kind == "long" or dur >= 3.0:
            n += 1
    return n


def _metric(
    metric_id: str, value: float | None, *, applicable: bool, confidence: float
) -> dict[str, Any]:
    return {
        "value": None if not applicable or value is None else round(float(value), 4),
        "unit": UNITS[metric_id],
        "applicable": bool(applicable and value is not None),
        "confidence": float(confidence) if applicable and value is not None else 0.0,
        "basis": "llm_judgment"
        if metric_id in {"ep_confident_language", "ep_recovery"}
        else "heuristic",
        "source": "S9" if metric_id == "ep_confident_language" else "H",
        "emotion_inference": False,
        "ser": False,
        "confidence_detection": False,
    }


def compute_energy_metrics(
    *,
    audio: dict[str, Any] | None = None,
    gesture: dict[str, Any] | None = None,
    expression: dict[str, Any] | None = None,
    content: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    pauses: dict[str, Any] | None = None,
    duration_s: float | None = None,
    expression_opt_in: bool = False,
) -> dict[str, Any] | None:
    """Return scoring-config energy_presence values, or None if nothing can be scored."""
    audio = audio or {}
    duration = float(
        duration_s
        or audio.get("duration_s")
        or (transcript or {}).get("duration")
        or 0.0
    )
    modalities: dict[str, list[dict[str, Any]]] = {}
    loudness = audio.get("intensity_windows") or []
    if loudness:
        modalities["loudness"] = list(loudness)
    pvq = audio.get("pvq_windows") or []
    if pvq:
        modalities["pvq"] = list(pvq)
    if gesture and gesture.get("activity_windows"):
        modalities["gesture"] = list(gesture["activity_windows"])
    if expression_opt_in and expression and expression.get("expressivity_windows"):
        modalities["expressivity"] = list(expression["expressivity_windows"])

    series = composite_energy(modalities, duration)
    used = sorted(modalities)
    trajectory = energy_trajectory(series, duration)
    keys = key_moment_times(content, transcript)
    lift = key_moment_lift(series, keys)

    soft = audio.get("too_soft_ratio")
    if soft is None and audio.get("intensity_voiced"):
        soft = too_soft_ratio(audio["intensity_voiced"])

    energy_block = (content or {}).get("energy") or {}
    conf_lang = energy_block.get("confident_language_level")
    recovery = energy_block.get("recovery_level")
    disruptions = disruption_count(pauses, content)
    recovery_applicable = disruptions > 0 and recovery is not None

    metrics = {
        "ep_too_soft_ratio": _metric(
            "ep_too_soft_ratio",
            float(soft) if isinstance(soft, (int, float)) else None,
            applicable=isinstance(soft, (int, float)),
            confidence=0.75,
        ),
        "ep_energy_trajectory": _metric(
            "ep_energy_trajectory",
            trajectory,
            applicable=trajectory is not None,
            confidence=0.55 + 0.1 * min(len(used), 4),
        ),
        "ep_key_moment_lift": _metric(
            "ep_key_moment_lift",
            lift,
            applicable=lift is not None,
            confidence=0.6,
        ),
        "ep_confident_language": _metric(
            "ep_confident_language",
            float(conf_lang) if isinstance(conf_lang, (int, float)) else None,
            applicable=isinstance(conf_lang, (int, float)),
            confidence=0.65,
        ),
        "ep_recovery": _metric(
            "ep_recovery",
            float(recovery)
            if recovery_applicable and isinstance(recovery, (int, float))
            else None,
            applicable=recovery_applicable,
            confidence=0.55,
        ),
    }
    if disruptions == 0:
        metrics["ep_recovery"]["failure_mode"] = "no_disruptions"
    elif recovery is None:
        metrics["ep_recovery"]["failure_mode"] = "llm_unavailable"

    if all(not row["applicable"] for row in metrics.values()):
        return None
    return {
        "label": "energy and presence signals",
        "confidence_detection": False,
        "ser": False,
        "emotion_inference": False,
        "modalities_used": used,
        "energy_series": series,
        "disruption_count": disruptions,
        "metrics": metrics,
    }
