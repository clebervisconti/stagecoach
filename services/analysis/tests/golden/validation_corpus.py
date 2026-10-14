"""Synthetic ≥20 min annotated corpora per language for metric validation start."""

from __future__ import annotations

from dataclasses import dataclass

from metrics.fluency import fl_filler_sounds_per_min
from metrics.pace import pp_unplanned_long_pauses_per_10min, pp_wpm
from metrics.types import PauseEvent, Word

MINUTES = 20.0
EN_WPM = 130.0
PT_WPM = 120.0
EN_FILLERS_PER_MIN = 5.0
PT_FILLERS_PER_MIN = 5.0
LONG_PAUSES_PER_10MIN = 1.0


@dataclass(frozen=True)
class Corpus:
    language: str
    words: list[Word]
    pauses: list[PauseEvent]
    expected_wpm: float
    expected_fillers_per_min: float
    expected_long_pauses_per_10min: float
    filler_sounds: tuple[str, ...]
    duration_s: float


def build_corpus(language: str) -> Corpus:
    """Timestamped words spanning ≥ 20 minutes. Not recorded audio."""
    if language == "pt-BR":
        wpm = PT_WPM
        filler = "éé"
        fillers = ("éé", "ahn", "ãh")
        token = "olá"
    else:
        wpm = EN_WPM
        filler = "um"
        fillers = ("um", "uh", "er")
        token = "hello"
        language = "en"
    duration_s = MINUTES * 60.0
    interval = 60.0 / wpm
    n_lexical = int(round(wpm * MINUTES))
    words = [
        Word(text=token, start=i * interval, end=i * interval + interval * 0.8)
        for i in range(n_lexical)
    ]
    n_fillers = int(round(EN_FILLERS_PER_MIN * MINUTES)) if language == "en" else int(
        round(PT_FILLERS_PER_MIN * MINUTES)
    )
    filler_gap = duration_s / max(n_fillers, 1)
    for i in range(n_fillers):
        t = min(duration_s - 0.2, (i + 0.5) * filler_gap)
        words.append(Word(text=filler, start=t, end=t + 0.15))
    words.sort(key=lambda w: w.start)
    n_long = int(round(LONG_PAUSES_PER_10MIN * (duration_s / 600.0)))
    pauses = [
        PauseEvent(start=120.0 + i * 300.0, end=123.5 + i * 300.0, position="mid_sentence")
        for i in range(n_long)
    ]
    return Corpus(
        language=language,
        words=words,
        pauses=pauses,
        expected_wpm=wpm,
        expected_fillers_per_min=float(n_fillers) / MINUTES,
        expected_long_pauses_per_10min=float(n_long) * 600.0 / duration_s,
        filler_sounds=fillers,
        duration_s=duration_s,
    )


def evaluate(corpus: Corpus) -> dict[str, float | str | bool]:
    wpm = pp_wpm(corpus.words, filler_sounds=corpus.filler_sounds)
    fillers = fl_filler_sounds_per_min(corpus.words, corpus.filler_sounds)
    pauses = pp_unplanned_long_pauses_per_10min(corpus.pauses, speaking_span_s=corpus.duration_s)

    def rel_err(got: float | None, expected: float) -> float:
        if got is None or expected == 0:
            return 1.0
        return abs(got - expected) / abs(expected)

    wpm_err = rel_err(wpm.value, corpus.expected_wpm)
    filler_err = rel_err(fillers.value, corpus.expected_fillers_per_min)
    pause_err = rel_err(pauses.value, corpus.expected_long_pauses_per_10min)
    return {
        "language": corpus.language,
        "duration_min": corpus.duration_s / 60.0,
        "n_words": len(corpus.words),
        "wpm_expected": corpus.expected_wpm,
        "wpm_got": wpm.value,
        "wpm_rel_err": wpm_err,
        "fillers_expected": corpus.expected_fillers_per_min,
        "fillers_got": fillers.value,
        "fillers_rel_err": filler_err,
        "pauses_expected": corpus.expected_long_pauses_per_10min,
        "pauses_got": pauses.value,
        "pauses_rel_err": pause_err,
        "within_5pct": wpm_err <= 0.05 and filler_err <= 0.05 and pause_err <= 0.05,
    }
