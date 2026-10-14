"""Time management metrics (category `time_management`, SPEC §4.4.16)."""

from __future__ import annotations

from typing import Optional, Sequence

from .types import MetricResult, SectionPlan


def tm_pct_of_slot(
    speaking_span_s: float,
    slot_s: Optional[float],
    *,
    planned_qa_s: float = 0.0,
    confidence: float = 1.0,
) -> MetricResult:
    """Speaking span ÷ (slot − planned Q&A, if Q&A is inside the slot).

    Units: ratio
    Source: heuristic (H). Gate: value > 1.15 caps the category at level 1.
    Failure modes: no slot → category N/A (`slot_length_not_provided`).
    """
    if slot_s is None or slot_s <= 0:
        return MetricResult(
            id="tm_pct_of_slot",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="slot_length_not_provided",
        )
    denom = slot_s - planned_qa_s
    if denom <= 0:
        return MetricResult(
            id="tm_pct_of_slot",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="slot_not_greater_than_planned_qa",
        )
    return MetricResult(
        id="tm_pct_of_slot",
        value=speaking_span_s / denom,
        unit="ratio",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def tm_section_variance(
    sections: Sequence[SectionPlan],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Mean absolute % deviation of actual vs planned section durations.

    Units: mean_abs_pct_deviation
    Source: heuristic (H). N/A without a talk plan.
    Failure modes: empty plan or a section with planned_s ≤ 0 → not applicable.
    """
    if not sections:
        return MetricResult(
            id="tm_section_variance",
            value=None,
            unit="mean_abs_pct_deviation",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="no_talk_plan",
        )
    if any(s.planned_s <= 0 for s in sections):
        return MetricResult(
            id="tm_section_variance",
            value=None,
            unit="mean_abs_pct_deviation",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="invalid_planned_duration",
        )
    deviations = [abs(s.actual_s - s.planned_s) / s.planned_s for s in sections]
    return MetricResult(
        id="tm_section_variance",
        value=sum(deviations) / len(deviations),
        unit="mean_abs_pct_deviation",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def tm_end_rush_events(
    *,
    rush_index: Optional[float],
    rush_phrase_hits: int = 0,
    skipped_slide_runs: int = 0,
    confidence: float = 1.0,
) -> MetricResult:
    """Count of end-rush signals: rush index > 1.15, rush phrases, skipped slides.

    Units: count
    Source: heuristic (H).
    Failure modes: none — missing rush_index simply contributes 0.
    """
    count = 0
    if rush_index is not None and rush_index > 1.15:
        count += 1
    count += max(0, rush_phrase_hits)
    count += max(0, skipped_slide_runs)
    return MetricResult(
        id="tm_end_rush_events",
        value=float(count),
        unit="count",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def tm_qa_time_protected(
    minutes_left_for_qa: Optional[float],
    planned_qa_min: Optional[float],
    *,
    confidence: float = 1.0,
) -> MetricResult:
    """Minutes left for Q&A ÷ planned Q&A minutes.

    Units: ratio
    Source: heuristic (H).
    Failure modes: no planned Q&A → not applicable.
    """
    if planned_qa_min is None or planned_qa_min <= 0 or minutes_left_for_qa is None:
        return MetricResult(
            id="tm_qa_time_protected",
            value=None,
            unit="ratio",
            basis="heuristic",
            source="H",
            confidence=confidence,
            applicable=False,
            failure_mode="no_planned_qa",
        )
    return MetricResult(
        id="tm_qa_time_protected",
        value=minutes_left_for_qa / planned_qa_min,
        unit="ratio",
        basis="heuristic",
        source="H",
        confidence=confidence,
    )


def compute_timing_metrics(
    *,
    speaking_span_s: float,
    slot_s: Optional[float] = None,
    planned_qa_s: float = 0.0,
    sections: Sequence[SectionPlan] = (),
    rush_index: Optional[float] = None,
    rush_phrase_hits: int = 0,
    skipped_slide_runs: int = 0,
    minutes_left_for_qa: Optional[float] = None,
    planned_qa_min: Optional[float] = None,
    confidence: float = 1.0,
) -> dict[str, MetricResult]:
    """Compute every `time_management` sub-metric listed in scoring.yaml."""
    return {
        "tm_pct_of_slot": tm_pct_of_slot(
            speaking_span_s, slot_s, planned_qa_s=planned_qa_s, confidence=confidence
        ),
        "tm_section_variance": tm_section_variance(sections, confidence=confidence),
        "tm_end_rush_events": tm_end_rush_events(
            rush_index=rush_index,
            rush_phrase_hits=rush_phrase_hits,
            skipped_slide_runs=skipped_slide_runs,
            confidence=confidence,
        ),
        "tm_qa_time_protected": tm_qa_time_protected(
            minutes_left_for_qa, planned_qa_min, confidence=confidence
        ),
    }
