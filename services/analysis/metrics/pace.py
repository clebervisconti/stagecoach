"""Pace & pausing metrics (category `pace_pausing`, SPEC §4.4.9)."""

from __future__ import annotations

import statistics
from typing import Iterable, Optional, Sequence

from .types import MetricResult, PauseEvent, Word

WINDOW_S = 30.0
HOP_S = 10.0
MIN_PAUSE_S = 0.250
BOUNDARY_PAUSE_MIN_S = 0.5
BOUNDARY_PAUSE_MAX_S = 2.0
LONG_PAUSE_S = 3.0


def _lexical_words(words: Sequence[Word], filler_sounds: Sequence[str]) -> list[Word]:
    fillers = {item.casefold() for item in filler_sounds}
    out: list[Word] = []
    for word in words:
        token = word.text.strip(".,!?;:").casefold()
        if token and token not in fillers:
            out.append(word)
    return out


def _speaking_span_s(words: Sequence[Word]) -> float:
    if not words:
        return 0.0
    return max(w.end for w in words) - min(w.start for w in words)


def _window_wpms(words: Sequence[Word], filler_sounds: Sequence[str]) -> list[float]:
    lexical = _lexical_words(words, filler_sounds)
    if not lexical:
        return []
    start = min(w.start for w in lexical)
    end = max(w.end for w in lexical)
    values: list[float] = []
    t = start
    while t + WINDOW_S <= end + 1e-9:
        t1 = t + WINDOW_S
        count = sum(1 for w in lexical if t <= w.start < t1)
        values.append(count / (WINDOW_S / 60.0))
        t += HOP_S
    return values


def pp_wpm(
    words: Sequence[Word],
    *,
    filler_sounds: Sequence[str] = (),
    confidence: float = 1.0,
) -> MetricResult:
    """Lexical words (excluding filler sounds) ÷ speaking-span minutes.

    Units: words_per_minute
    Source: heuristic (H_S13). Bands are context/language-specific in scoring.yaml.
    Failure modes: no lexical words or zero span → value None, not applicable.
    """
    lexical = _lexical_words(words, filler_sounds)
    span = _speaking_span_s(lexical)
    if not lexical or span <= 0:
        return MetricResult(
            id="pp_wpm",
            value=None,
            unit="words_per_minute",
            basis="heuristic",
            source="H_S13",
            confidence=confidence,
            applicable=False,
            failure_mode="no_lexical_words_or_zero_span",
        )
    return MetricResult(
        id="pp_wpm",
        value=len(lexical) / (span / 60.0),
        unit="words_per_minute",
        basis="heuristic",
        source="H_S13",
        confidence=confidence,
    )


def pp_articulation_rate_sps(
    syllable_count: int,
    phonation_time_s: float,
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Syllables ÷ phonation time (pauses ≥ 250 ms removed) [S25].

    Units: syllables_per_second
    Source: research (S25). Informational (weight 0) until calibrated.
    Failure modes: phonation_time_s ≤ 0 → not applicable.
    """
    if phonation_time_s <= 0 or syllable_count < 0:
        return MetricResult(
            id="pp_articulation_rate_sps",
            value=None,
            unit="syllables_per_second",
            basis="research",
            source="S25",
            confidence=confidence,
            applicable=False,
            failure_mode="no_phonation",
        )
    return MetricResult(
        id="pp_articulation_rate_sps",
        value=syllable_count / phonation_time_s,
        unit="syllables_per_second",
        basis="research",
        source="S25",
        confidence=confidence,
    )


def pp_pace_cv(
    words: Sequence[Word],
    *,
    filler_sounds: Sequence[str] = (),
    confidence: float = 1.0,
) -> MetricResult:
    """Coefficient of variation of WPM over 30-s windows (hop 10 s).

    Units: coefficient_of_variation
    Source: heuristic (H).
    Failure modes: fewer than two windows or zero mean → not applicable.
    """
    wpms = _window_wpms(words, filler_sounds)
    if len(wpms) < 2:
        return MetricResult(
            id="pp_pace_cv",
            value=None,
            unit="coefficient_of_variation",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="insufficient_windows",
        )
    mean = statistics.fmean(wpms)
    if mean == 0:
        return MetricResult(
            id="pp_pace_cv",
            value=None,
            unit="coefficient_of_variation",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="zero_mean_wpm",
        )
    return MetricResult(
        id="pp_pace_cv",
        value=statistics.pstdev(wpms) / mean,
        unit="coefficient_of_variation",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def pp_rush_index(
    words: Sequence[Word],
    *,
    filler_sounds: Sequence[str] = (),
    confidence: float = 1.0,
) -> MetricResult:
    """Median WPM in the final 20% ÷ overall median WPM.

    Units: ratio
    Source: heuristic (H).
    Failure modes: empty last-20% or overall median 0 → not applicable.
    """
    lexical = _lexical_words(words, filler_sounds)
    if len(lexical) < 2:
        return MetricResult(
            id="pp_rush_index",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="insufficient_words",
        )
    start = min(w.start for w in lexical)
    end = max(w.end for w in lexical)
    cutoff = start + 0.8 * (end - start)
    overall_windows = _window_wpms(lexical, ())
    last = [w for w in lexical if w.start >= cutoff]
    last_span = _speaking_span_s(last)
    if not overall_windows or last_span <= 0 or not last:
        return MetricResult(
            id="pp_rush_index",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="empty_final_window",
        )
    overall_median = statistics.median(overall_windows)
    if overall_median == 0:
        return MetricResult(
            id="pp_rush_index",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="zero_overall_median",
        )
    last_wpm = len(last) / (last_span / 60.0)
    return MetricResult(
        id="pp_rush_index",
        value=last_wpm / overall_median,
        unit="ratio",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def pp_boundary_pause_ratio(
    boundaries: Sequence[float],
    pauses: Sequence[PauseEvent],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Share of sentence/section boundaries followed by a 0.5–2.0 s pause.

    Units: ratio
    Source: heuristic (H).
    Failure modes: no boundaries → not applicable.
    """
    if not boundaries:
        return MetricResult(
            id="pp_boundary_pause_ratio",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="no_boundaries",
        )
    hits = 0
    for t in boundaries:
        for pause in pauses:
            if pause.start < t - 0.05:
                continue
            if pause.start - t > 0.25:
                continue
            if BOUNDARY_PAUSE_MIN_S <= pause.duration <= BOUNDARY_PAUSE_MAX_S:
                hits += 1
                break
    return MetricResult(
        id="pp_boundary_pause_ratio",
        value=hits / len(boundaries),
        unit="ratio",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def pp_unplanned_long_pauses_per_10min(
    pauses: Sequence[PauseEvent],
    *,
    speaking_span_s: float,
    confidence: float = 1.0,
) -> MetricResult:
    """Mid-sentence silences ≥ 3 s, scaled to 10 minutes.

    Units: per_10min
    Source: heuristic (H).
    Failure modes: speaking_span_s ≤ 0 → not applicable.
    """
    if speaking_span_s <= 0:
        return MetricResult(
            id="pp_unplanned_long_pauses_per_10min",
            value=None,
            unit="per_10min",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="zero_speaking_span",
        )
    count = sum(
        1
        for p in pauses
        if p.duration >= LONG_PAUSE_S and p.position == "mid_sentence"
    )
    return MetricResult(
        id="pp_unplanned_long_pauses_per_10min",
        value=count * (600.0 / speaking_span_s),
        unit="per_10min",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def pp_mean_length_of_run(
    words: Sequence[Word],
    pauses: Sequence[PauseEvent],
    *,
    filler_sounds: Sequence[str] = (),
    confidence: float = 1.0,
) -> MetricResult:
    """Mean words between pauses ≥ 250 ms.

    Units: words
    Source: heuristic (H).
    Failure modes: no lexical words → not applicable.
    """
    lexical = _lexical_words(words, filler_sounds)
    if not lexical:
        return MetricResult(
            id="pp_mean_length_of_run",
            value=None,
            unit="words",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="no_lexical_words",
        )
    cuts = sorted(p.end for p in pauses if p.duration >= MIN_PAUSE_S)
    runs: list[int] = []
    count = 0
    cut_i = 0
    for word in sorted(lexical, key=lambda w: w.start):
        while cut_i < len(cuts) and cuts[cut_i] <= word.start:
            if count:
                runs.append(count)
                count = 0
            cut_i += 1
        count += 1
    if count:
        runs.append(count)
    return MetricResult(
        id="pp_mean_length_of_run",
        value=statistics.fmean(runs) if runs else float(len(lexical)),
        unit="words",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def compute_pace_metrics(
    words: Sequence[Word],
    pauses: Sequence[PauseEvent],
    *,
    filler_sounds: Sequence[str] = (),
    syllable_count: int = 0,
    phonation_time_s: float = 0.0,
    boundaries: Optional[Iterable[float]] = None,
    confidence: float = 1.0,
) -> dict[str, MetricResult]:
    """Compute every `pace_pausing` sub-metric listed in scoring.yaml."""
    lexical = _lexical_words(words, filler_sounds)
    span = _speaking_span_s(lexical)
    if boundaries is None:
        boundaries = [w.end for w in words if w.text.rstrip().endswith((".", "!", "?"))]
    boundary_list = list(boundaries)
    return {
        "pp_wpm": pp_wpm(words, filler_sounds=filler_sounds, confidence=confidence),
        "pp_articulation_rate_sps": pp_articulation_rate_sps(
            syllable_count, phonation_time_s, confidence=confidence
        ),
        "pp_pace_cv": pp_pace_cv(words, filler_sounds=filler_sounds, confidence=confidence),
        "pp_rush_index": pp_rush_index(words, filler_sounds=filler_sounds, confidence=confidence),
        "pp_boundary_pause_ratio": pp_boundary_pause_ratio(
            boundary_list, pauses, confidence=confidence
        ),
        "pp_unplanned_long_pauses_per_10min": pp_unplanned_long_pauses_per_10min(
            pauses, speaking_span_s=span, confidence=confidence
        ),
        "pp_mean_length_of_run": pp_mean_length_of_run(
            words, pauses, filler_sounds=filler_sounds, confidence=confidence
        ),
    }
