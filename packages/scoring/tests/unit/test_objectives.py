"""Objective check engine (SPEC §9.7 / issue #62). No live LLM."""

import pytest

from scoring.objectives import (
    evaluate_check,
    llm_check,
    metric_threshold,
    needleman_wunsch,
    objectives_score,
    outline_alignment,
    per_slide_threshold,
    prep_objectives,
)


def test_outline_alignment_perfect_and_reordered():
    perfect = outline_alignment(["A", "B", "C"], ["A", "B", "C"])
    assert perfect.status == "met"
    assert perfect.score == pytest.approx(1.0)
    swapped = needleman_wunsch(["A", "B", "C"], ["A", "C", "B"])
    assert swapped.status in {"partial", "not_met", "met"}
    assert 0.0 <= swapped.score <= 1.0
    empty = outline_alignment([], [])
    assert empty.status == "na"


def test_metric_threshold_bands_and_window():
    assert metric_threshold(0.90, comparator="<=", target=0.92).status == "met"
    partial = metric_threshold(0.96, comparator="<=", target=0.92, window=0.05)
    assert partial.status == "partial"
    assert partial.score == 0.5
    missed = metric_threshold(1.10, comparator="<=", target=0.92, window=0.05)
    assert missed.status == "not_met"
    assert metric_threshold(None, comparator="<=", target=0.92).status == "na"
    assert metric_threshold(0.75, comparator=">=", target=0.70).status == "met"


def test_per_slide_threshold():
    rows = per_slide_threshold(
        {"5": 0.10, "6": 0.28, "7": None},
        comparator="<=",
        target=0.20,
        window=0.10,
    )
    assert [row.status for row in rows] == ["met", "partial", "na"]


def test_llm_check_uses_provided_match_not_a_client():
    met = llm_check("cta", "llm_semantic_match", 0.9, timing_ok=True)
    assert met.status == "met"
    late = llm_check("open", "llm_semantic_match", 0.9, timing_ok=False)
    assert late.status == "partial"
    missing = llm_check("story", "llm_presence", None)
    assert missing.status == "na"


def test_objectives_score_partial_is_half():
    rows = [
        evaluate_check(
            objective_id="a",
            check_type="metric_threshold",
            value=0.9,
            comparator="<=",
            target=0.92,
        ),
        evaluate_check(
            objective_id="b",
            check_type="metric_threshold",
            value=0.96,
            comparator="<=",
            target=0.92,
            window=0.05,
        ),
        evaluate_check(objective_id="c", check_type="llm_presence", match=None),
    ]
    assert objectives_score(rows) == pytest.approx(0.75)


def test_prep_objectives_v1_has_check_types():
    body = prep_objectives(
        {"title": "Pilot", "must_include": "Acme outage", "goal": "book a workshop"}
    )
    assert body["prompt_id"] == "prep_objectives_v1"
    types = {row["check_type"] for row in body["objectives"]}
    assert "llm_semantic_match" in types
    assert "llm_presence" in types
    assert "outline_alignment" in types
    assert "metric_threshold" in types
