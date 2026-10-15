"""Objective check engine (SPEC §9.7 / issue #62).

Alignment and thresholds are code. LLM check types accept a provided match
score so tests never call a paid model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

Status = Literal["met", "partial", "not_met", "na"]


@dataclass(frozen=True)
class AlignmentResult:
    score: float
    planned: list[str]
    actual: list[str]
    status: Status


@dataclass(frozen=True)
class ObjectiveResult:
    objective_id: str
    check_type: str
    status: Status
    score: float | None
    evidence: list[str]


def outline_alignment(planned: Sequence[str], actual: Sequence[str]) -> AlignmentResult:
    """outline_alignment check type: Needleman–Wunsch on section labels."""
    return needleman_wunsch(list(planned), list(actual))


def needleman_wunsch(
    planned: list[str],
    actual: list[str],
    *,
    match: int = 2,
    mismatch: int = -1,
    gap: int = -1,
) -> AlignmentResult:
    """Global alignment of planned vs detected section labels."""
    if not planned and not actual:
        return AlignmentResult(score=1.0, planned=[], actual=[], status="na")
    n = len(planned)
    m = len(actual)
    grid = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        grid[i][0] = i * gap
    for j in range(1, m + 1):
        grid[0][j] = j * gap
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = grid[i - 1][j - 1] + (match if planned[i - 1] == actual[j - 1] else mismatch)
            grid[i][j] = max(diag, grid[i - 1][j] + gap, grid[i][j - 1] + gap)
    raw = grid[n][m]
    perfect = match * max(n, m, 1)
    worst = gap * (n + m) if (n + m) else 0
    span = perfect - worst
    norm = 1.0 if span == 0 else (raw - worst) / span
    norm = max(0.0, min(1.0, norm))
    return AlignmentResult(score=norm, planned=planned, actual=actual, status=_band(norm))


def _band(value: float) -> Status:
    if value >= 0.8:
        return "met"
    if value >= 0.5:
        return "partial"
    return "not_met"


def metric_threshold(
    value: float | None,
    *,
    comparator: str,
    target: float,
    window: float | None = None,
) -> ObjectiveResult:
    if value is None:
        return ObjectiveResult("metric", "metric_threshold", "na", None, ["value missing"])
    ok = _compare(value, comparator, target)
    if ok:
        status: Status = "met"
        score = 1.0
    else:
        if window is not None:
            relaxed = target + window if comparator.startswith("<") else target - window
            near = _compare(value, comparator, relaxed)
        else:
            near = False
        if near:
            status = "partial"
            score = 0.5
        else:
            status = "not_met"
            score = 0.0
    return ObjectiveResult(
        "metric",
        "metric_threshold",
        status,
        score,
        [f"{value} {comparator} {target}"],
    )


def _compare(value: float, comparator: str, target: float) -> bool:
    if comparator in {"<=", "le"}:
        return value <= target
    if comparator in {">=", "ge"}:
        return value >= target
    if comparator in {"<", "lt"}:
        return value < target
    if comparator in {">", "gt"}:
        return value > target
    return value == target


def llm_check(
    objective_id: str,
    check_type: str,
    match: float | None,
    *,
    timing_ok: bool | None = None,
) -> ObjectiveResult:
    """llm_semantic_match / llm_presence using a provided match in [0, 1]."""
    if match is None:
        return ObjectiveResult(objective_id, check_type, "na", None, ["no match available"])
    status = _band(match)
    if timing_ok is False:
        status = "partial" if match >= 0.5 else "not_met"
    score = {"met": 1.0, "partial": 0.5, "not_met": 0.0, "na": None}[status]
    evidence = [f"match={match}"]
    if timing_ok is not None:
        evidence.append(f"timing_ok={timing_ok}")
    return ObjectiveResult(objective_id, check_type, status, score, evidence)


def objectives_score(results: list[ObjectiveResult]) -> float | None:
    """Share met; partial counts as 0.5. N/A ignored."""
    usable = [row for row in results if row.status != "na"]
    if not usable:
        return None
    total = 0.0
    for row in usable:
        if row.status == "met":
            total += 1.0
        elif row.status == "partial":
            total += 0.5
    return total / len(usable)


def per_slide_threshold(
    slide_values: Mapping[str, float | None],
    *,
    comparator: str,
    target: float,
    window: float | None = None,
) -> list[ObjectiveResult]:
    """metric_threshold per slide (e.g. va_reading_ratio on slides 5–9)."""
    results: list[ObjectiveResult] = []
    for slide_id, value in slide_values.items():
        row = metric_threshold(value, comparator=comparator, target=target, window=window)
        results.append(
            ObjectiveResult(
                f"slide:{slide_id}",
                "metric_threshold",
                row.status,
                row.score,
                [*row.evidence, f"slide={slide_id}"],
            )
        )
    return results


def evaluate_check(
    *,
    objective_id: str,
    check_type: str,
    planned: Sequence[str] | None = None,
    actual: Sequence[str] | None = None,
    value: float | None = None,
    comparator: str = "<=",
    target: float = 0.0,
    window: float | None = None,
    match: float | None = None,
    timing_ok: bool | None = None,
) -> ObjectiveResult:
    if check_type == "outline_alignment":
        result = outline_alignment(list(planned or []), list(actual or []))
        return ObjectiveResult(
            objective_id,
            check_type,
            result.status,
            result.score,
            ["needleman_wunsch"],
        )
    if check_type in {"llm_semantic_match", "llm_presence"}:
        return llm_check(objective_id, check_type, match, timing_ok=timing_ok)
    if check_type in {"metric_threshold", "metric_threshold_per_slide"}:
        row = metric_threshold(value, comparator=comparator, target=target, window=window)
        return ObjectiveResult(objective_id, check_type, row.status, row.score, row.evidence)
    raise ValueError(f"unknown check_type: {check_type}")


def prep_objectives(plan: Mapping[str, Any]) -> dict[str, Any]:
    """prep_objectives_v1 stand-in: measurable checks from a plan. No live LLM."""
    title = str(plan.get("title") or "this talk")
    story = str(plan.get("must_include") or "the key story")
    cta = str(plan.get("goal") or "name a dated next step")
    return {
        "prompt_id": "prep_objectives_v1",
        "objectives": [
            {
                "id": "core_message_open",
                "check_type": "llm_semantic_match",
                "text": "State the core message within the first 90 s",
                "timing": "t<=90",
            },
            {
                "id": "core_message_close",
                "check_type": "llm_semantic_match",
                "text": "Repeat the core message in the close",
                "window": "last_90s",
            },
            {
                "id": "key_story",
                "check_type": "llm_presence",
                "text": f"Include {story}",
            },
            {
                "id": "outline_order",
                "check_type": "outline_alignment",
                "text": f"Cover planned sections for {title} in order",
            },
            {
                "id": "slot_finish",
                "check_type": "metric_threshold",
                "text": "Finish at ≤ 92% of the slot",
                "metric": "tm_pct_of_slot",
                "comparator": "<=",
                "target": 0.92,
            },
            {
                "id": "cta",
                "check_type": "llm_semantic_match",
                "text": f"Deliver the CTA: {cta}",
            },
        ],
    }
