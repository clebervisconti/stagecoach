"""Vocal variety & prosody metrics (category `vocal_variety`, SPEC §4.4.10)."""

from __future__ import annotations

import math
import statistics
from typing import Optional, Sequence

from .types import MetricResult, ProsodyFrame

PVQ_WINDOW_S = 10.0
PVQ_MIN_VOICED_S = 3.0
MONOTONE_WINDOW_S = 30.0
MONOTONE_PVQ = 0.08
MONOTONE_RANGE_ST = 3.0
INTENSITY_WINDOW_S = 10.0


def _frames_in(frames: Sequence[ProsodyFrame], start: float, end: float) -> list[ProsodyFrame]:
    return [f for f in frames if start <= f.time_s < end]


def _voiced_hz(frames: Sequence[ProsodyFrame]) -> list[float]:
    return [
        f.f0_hz
        for f in frames
        if f.voiced and f.f0_hz is not None and f.f0_hz > 0 and math.isfinite(f.f0_hz)
    ]


def _voiced_st(frames: Sequence[ProsodyFrame]) -> list[float]:
    return [
        f.f0_st
        for f in frames
        if f.voiced and f.f0_st is not None and math.isfinite(f.f0_st)
    ]


def _voiced_db(frames: Sequence[ProsodyFrame]) -> list[float]:
    return [
        f.intensity_db
        for f in frames
        if f.voiced and f.intensity_db is not None and math.isfinite(f.intensity_db)
    ]


def _window_starts(frames: Sequence[ProsodyFrame], width: float) -> list[float]:
    if not frames:
        return []
    t0 = frames[0].time_s
    t1 = frames[-1].time_s
    starts: list[float] = []
    t = t0
    while t < t1:
        starts.append(t)
        t += width
    return starts


def _pvq(values_hz: Sequence[float]) -> Optional[float]:
    if len(values_hz) < 2:
        return None
    mean = statistics.fmean(values_hz)
    if mean <= 0:
        return None
    return statistics.pstdev(values_hz) / mean


def vv_pvq_median(
    frames: Sequence[ProsodyFrame],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Median over 10-s windows (≥ 3 s voiced) of SD(F0 Hz)/mean(F0 Hz) [S24].

    Units: ratio
    Source: research (S24).
    Failure modes: no window with ≥ 3 s voiced F0 → not applicable.
    """
    values: list[float] = []
    for start in _window_starts(frames, PVQ_WINDOW_S):
        window = _frames_in(frames, start, start + PVQ_WINDOW_S)
        hz = _voiced_hz(window)
        if len(hz) < 2:
            continue
        step = PVQ_WINDOW_S / max(len(window), 1)
        if len(hz) * step < PVQ_MIN_VOICED_S:
            continue
        pvq = _pvq(hz)
        if pvq is not None:
            values.append(pvq)
    if not values:
        return MetricResult(
            id="vv_pvq_median",
            value=None,
            unit="ratio",
            basis="research",
            source="S24",
            confidence=confidence,
            applicable=False,
            failure_mode="insufficient_voiced_windows",
        )
    return MetricResult(
        id="vv_pvq_median",
        value=statistics.median(values),
        unit="ratio",
        basis="research",
        source="S24",
        confidence=confidence,
    )


def vv_pitch_range_st(
    frames: Sequence[ProsodyFrame],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Median per-window (P95 − P5) of F0 in speaker-relative semitones.

    Units: semitones
    Source: heuristic (H).
    Failure modes: no voiced windows → not applicable.
    """
    values: list[float] = []
    for start in _window_starts(frames, PVQ_WINDOW_S):
        st = _voiced_st(_frames_in(frames, start, start + PVQ_WINDOW_S))
        if len(st) < 5:
            continue
        ordered = sorted(st)
        p5 = ordered[max(0, int(0.05 * (len(ordered) - 1)))]
        p95 = ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))]
        values.append(p95 - p5)
    if not values:
        return MetricResult(
            id="vv_pitch_range_st",
            value=None,
            unit="semitones",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="insufficient_voiced_windows",
        )
    return MetricResult(
        id="vv_pitch_range_st",
        value=statistics.median(values),
        unit="semitones",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def vv_monotone_windows_ratio(
    frames: Sequence[ProsodyFrame],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Share of 30-s windows with PVQ < 0.08 and pitch range < 3 st.

    Units: ratio
    Source: heuristic (H).
    Failure modes: no 30-s windows with voiced speech → not applicable.
    """
    starts = _window_starts(frames, MONOTONE_WINDOW_S)
    scored = 0
    monotone = 0
    for start in starts:
        window = _frames_in(frames, start, start + MONOTONE_WINDOW_S)
        hz = _voiced_hz(window)
        st = _voiced_st(window)
        if len(hz) < 2 or len(st) < 5:
            continue
        pvq = _pvq(hz)
        ordered = sorted(st)
        p5 = ordered[max(0, int(0.05 * (len(ordered) - 1)))]
        p95 = ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))]
        if pvq is None:
            continue
        scored += 1
        if pvq < MONOTONE_PVQ and (p95 - p5) < MONOTONE_RANGE_ST:
            monotone += 1
    if scored == 0:
        return MetricResult(
            id="vv_monotone_windows_ratio",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="insufficient_windows",
        )
    return MetricResult(
        id="vv_monotone_windows_ratio",
        value=monotone / scored,
        unit="ratio",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def vv_intensity_variation_db(
    frames: Sequence[ProsodyFrame],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Median per-window SD of intensity (dB) over voiced frames.

    Units: decibels
    Source: heuristic (H). Mic-dependent; callers should cap confidence at 0.7.
    Failure modes: fewer than two voiced intensity samples per window → N/A.
    """
    values: list[float] = []
    for start in _window_starts(frames, INTENSITY_WINDOW_S):
        db = _voiced_db(_frames_in(frames, start, start + INTENSITY_WINDOW_S))
        if len(db) < 2:
            continue
        values.append(statistics.pstdev(db))
    if not values:
        return MetricResult(
            id="vv_intensity_variation_db",
            value=None,
            unit="decibels",
            basis="heuristic",
            source="H",
            confidence=min(confidence, 0.7),
            applicable=False,
            failure_mode="insufficient_voiced_intensity",
        )
    return MetricResult(
        id="vv_intensity_variation_db",
        value=statistics.median(values),
        unit="decibels",
        basis="heuristic",
        source="H",
        confidence=min(confidence, 0.7),
    )


def vv_emphasis_rate_per_min(
    frames: Sequence[ProsodyFrame],
    *,
    duration_s: Optional[float] = None,
    threshold: float = 1.5,
    confidence: float = 1.0,
) -> MetricResult:
    """Prominences per minute: local maxima of z(F0)+z(intensity) above threshold.

    Units: per_minute
    Source: heuristic (H), experimental.
    Failure modes: duration ≤ 0 or fewer than 3 voiced frames → not applicable.
    """
    voiced = [f for f in frames if f.voiced and f.f0_st is not None and f.intensity_db is not None]
    span = duration_s if duration_s is not None else (
        (frames[-1].time_s - frames[0].time_s) if len(frames) >= 2 else 0.0
    )
    if span <= 0 or len(voiced) < 3:
        return MetricResult(
            id="vv_emphasis_rate_per_min",
            value=None,
            unit="per_minute",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="insufficient_voiced_frames",
        )
    st = [f.f0_st for f in voiced if f.f0_st is not None]
    db = [f.intensity_db for f in voiced if f.intensity_db is not None]
    st_mean, db_mean = statistics.fmean(st), statistics.fmean(db)
    st_sd = statistics.pstdev(st) or 1.0
    db_sd = statistics.pstdev(db) or 1.0
    combo = [((s - st_mean) / st_sd) + ((d - db_mean) / db_sd) for s, d in zip(st, db)]
    peaks = 0
    for i in range(1, len(combo) - 1):
        if combo[i] > threshold and combo[i] >= combo[i - 1] and combo[i] >= combo[i + 1]:
            peaks += 1
    return MetricResult(
        id="vv_emphasis_rate_per_min",
        value=peaks / (span / 60.0),
        unit="per_minute",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def compute_prosody_metrics(
    frames: Sequence[ProsodyFrame],
    *,
    duration_s: Optional[float] = None,
    confidence: float = 1.0,
    music_flag: bool = False,
) -> dict[str, MetricResult]:
    """Compute every `vocal_variety` sub-metric listed in scoring.yaml."""
    if music_flag:
        na = MetricResult(
            id="",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=0.0,
            applicable=False,
            failure_mode="background_music",
        )
        return {
            "vv_pvq_median": MetricResult(**{**na.to_dict(), "id": "vv_pvq_median", "unit": "ratio"}),
            "vv_pitch_range_st": MetricResult(
                **{**na.to_dict(), "id": "vv_pitch_range_st", "unit": "semitones"}
            ),
            "vv_monotone_windows_ratio": MetricResult(
                **{**na.to_dict(), "id": "vv_monotone_windows_ratio", "unit": "ratio"}
            ),
            "vv_intensity_variation_db": MetricResult(
                **{**na.to_dict(), "id": "vv_intensity_variation_db", "unit": "decibels"}
            ),
            "vv_emphasis_rate_per_min": MetricResult(
                **{**na.to_dict(), "id": "vv_emphasis_rate_per_min", "unit": "per_minute"}
            ),
        }
    return {
        "vv_pvq_median": vv_pvq_median(frames, confidence=confidence),
        "vv_pitch_range_st": vv_pitch_range_st(frames, confidence=confidence),
        "vv_monotone_windows_ratio": vv_monotone_windows_ratio(frames, confidence=confidence),
        "vv_intensity_variation_db": vv_intensity_variation_db(frames, confidence=confidence),
        "vv_emphasis_rate_per_min": vv_emphasis_rate_per_min(
            frames, duration_s=duration_s, confidence=confidence
        ),
    }
