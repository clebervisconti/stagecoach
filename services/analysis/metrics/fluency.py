"""Fluency & language metrics (category `fluency`, SPEC §4.4.11)."""

from __future__ import annotations

import re
from typing import Optional, Sequence

from .types import MetricResult, Word

# Laske & DiGennaro Reed 2024 [S12]: ≤5/min no measurable penalty; ~12/min harmful.
FILLER_BENCHMARK_NO_PENALTY = 5.0
FILLER_BENCHMARK_HARMFUL = 12.0

WORD_RE = re.compile(r"[\wÀ-ÿ'-]+", re.UNICODE)


def _speaking_minutes(words: Sequence[Word]) -> float:
    if not words:
        return 0.0
    span = max(w.end for w in words) - min(w.start for w in words)
    return span / 60.0


def _normalize(text: str) -> str:
    return text.strip(".,!?;:").casefold()


def fl_filler_sounds_per_min(
    words: Sequence[Word],
    filler_sounds: Sequence[str],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """um/uh/er/ah/hmm (en); éé/ahn/ãh/hum (pt) per speaking minute.

    Units: per_minute
    Source: research (S12). Breakpoints at 5 and 12 are R; the rest is H.
    Failure modes: speaking span ≤ 0 → not applicable.
    """
    minutes = _speaking_minutes(words)
    if minutes <= 0:
        return MetricResult(
            id="fl_filler_sounds_per_min",
            value=None,
            unit="per_minute",
            basis="research",
            source="S12",
            confidence=confidence,
            applicable=False,
            failure_mode="zero_speaking_span",
        )
    lexicon = {item.casefold() for item in filler_sounds}
    count = sum(1 for w in words if _normalize(w.text) in lexicon)
    return MetricResult(
        id="fl_filler_sounds_per_min",
        value=count / minutes,
        unit="per_minute",
        basis="research",
        source="S12",
        confidence=confidence,
    )


def fl_filler_words_per_min(
    confirmed_filler_words: Sequence[Word],
    words: Sequence[Word],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Filler words the LLM confirmed as non-lexical, per speaking minute.

    Units: per_minute
    Source: research (S12).
    Failure modes: speaking span ≤ 0 → not applicable.
    Unconfirmed candidates are ignored (not counted).
    """
    minutes = _speaking_minutes(words)
    if minutes <= 0:
        return MetricResult(
            id="fl_filler_words_per_min",
            value=None,
            unit="per_minute",
            basis="research",
            source="S12",
            confidence=confidence,
            applicable=False,
            failure_mode="zero_speaking_span",
        )
    return MetricResult(
        id="fl_filler_words_per_min",
        value=len(confirmed_filler_words) / minutes,
        unit="per_minute",
        basis="research",
        source="S12",
        confidence=confidence,
    )


def fl_hedges_apologies_per_10min(
    transcript_text: str,
    hedges: Sequence[str],
    apologies: Sequence[str],
    *,
    speaking_span_s: float,
    confidence: float = 1.0,
) -> MetricResult:
    """Hedges and unnecessary apologies scaled to 10 minutes.

    Units: per_10min
    Source: heuristic (H).
    Failure modes: speaking_span_s ≤ 0 → not applicable.
    """
    if speaking_span_s <= 0:
        return MetricResult(
            id="fl_hedges_apologies_per_10min",
            value=None,
            unit="per_10min",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="zero_speaking_span",
        )
    haystack = transcript_text.casefold()
    count = 0
    for phrase in list(hedges) + list(apologies):
        needle = phrase.casefold()
        start = 0
        while True:
            idx = haystack.find(needle, start)
            if idx < 0:
                break
            count += 1
            start = idx + max(len(needle), 1)
    return MetricResult(
        id="fl_hedges_apologies_per_10min",
        value=count * (600.0 / speaking_span_s),
        unit="per_10min",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def fl_repetitions_restarts_per_min(
    words: Sequence[Word],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Immediate word or phrase repetitions and restarts per speaking minute.

    Units: per_minute
    Source: heuristic (H).
    Failure modes: speaking span ≤ 0 → not applicable.
    """
    minutes = _speaking_minutes(words)
    if minutes <= 0:
        return MetricResult(
            id="fl_repetitions_restarts_per_min",
            value=None,
            unit="per_minute",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="zero_speaking_span",
        )
    tokens = [_normalize(w.text) for w in words if WORD_RE.search(w.text)]
    count = 0
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i] and tokens[i] == tokens[i + 1]:
            count += 1
            i += 2
            continue
        if (
            i + 3 < len(tokens)
            and tokens[i]
            and tokens[i : i + 2] == tokens[i + 2 : i + 4]
        ):
            count += 1
            i += 4
            continue
        i += 1
    return MetricResult(
        id="fl_repetitions_restarts_per_min",
        value=count / minutes,
        unit="per_minute",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def fl_grammar_llm(
    level: Optional[float],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """LLM grammar/word-choice issues that impede understanding (not accent).

    Units: llm_level
    Source: LLM judgment (S33).
    Failure modes: no LLM level → not applicable (insufficient_evidence).
    """
    if level is None:
        return MetricResult(
            id="fl_grammar_llm",
            value=None,
            unit="llm_level",
            basis="llm_judgment",
            source="S33",
            confidence=confidence,
            applicable=False,
            failure_mode="insufficient_evidence",
        )
    return MetricResult(
        id="fl_grammar_llm",
        value=float(level),
        unit="llm_level",
        basis="llm_judgment",
        source="S33",
        confidence=confidence,
    )


def combined_filler_rate(
    sounds_per_min: Optional[float],
    words_per_min: Optional[float],
) -> Optional[float]:
    """Sounds plus confirmed filler words (SPEC §4.4.11 combined rate)."""
    if sounds_per_min is None and words_per_min is None:
        return None
    return (sounds_per_min or 0.0) + (words_per_min or 0.0)


def filler_benchmark_note(combined_per_min: Optional[float]) -> dict:
    """Place the combined rate next to the 5/min and 12/min [S12] anchors."""
    return {
        "combined_per_min": combined_per_min,
        "no_penalty_at_or_below": FILLER_BENCHMARK_NO_PENALTY,
        "harmful_at": FILLER_BENCHMARK_HARMFUL,
        "source": "S12",
        "label": (
            "≤ 5/min: no measurable penalty in the study; ~12/min: clearly harmful"
        ),
    }


def compute_fluency_metrics(
    words: Sequence[Word],
    *,
    filler_sounds: Sequence[str] = (),
    confirmed_filler_words: Sequence[Word] = (),
    hedges: Sequence[str] = (),
    apologies: Sequence[str] = (),
    transcript_text: str = "",
    grammar_level: Optional[float] = None,
    confidence: float = 1.0,
    filler_preserving_asr: bool = True,
) -> dict[str, MetricResult]:
    """Compute every `fluency` sub-metric listed in scoring.yaml."""
    if not filler_preserving_asr:
        confidence = min(confidence, 0.5)
    minutes_span_s = _speaking_minutes(words) * 60.0
    text = transcript_text or " ".join(w.text for w in words)
    results = {
        "fl_filler_sounds_per_min": fl_filler_sounds_per_min(
            words, filler_sounds, confidence=confidence
        ),
        "fl_filler_words_per_min": fl_filler_words_per_min(
            confirmed_filler_words, words, confidence=confidence
        ),
        "fl_hedges_apologies_per_10min": fl_hedges_apologies_per_10min(
            text, hedges, apologies, speaking_span_s=minutes_span_s, confidence=confidence
        ),
        "fl_repetitions_restarts_per_min": fl_repetitions_restarts_per_min(
            words, confidence=confidence
        ),
        "fl_grammar_llm": fl_grammar_llm(grammar_level, confidence=confidence),
    }
    return results
