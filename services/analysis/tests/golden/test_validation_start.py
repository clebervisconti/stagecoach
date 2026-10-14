"""Metric-level validation start on ≥ 20 min annotated audio per language."""

from __future__ import annotations

from tests.golden.validation_corpus import MINUTES, build_corpus, evaluate


def test_en_and_ptbr_corpora_are_at_least_twenty_minutes():
    for language in ("en", "pt-BR"):
        corpus = build_corpus(language)
        assert corpus.duration_s / 60.0 >= MINUTES
        result = evaluate(corpus)
        assert result["within_5pct"] is True
        assert result["wpm_rel_err"] <= 0.05
        assert result["fillers_rel_err"] <= 0.05
        assert result["pauses_rel_err"] <= 0.05
