"""tm_section_variance, planned-vs-actual table, rehearsal progress (issue #63)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SectionRow:
    section: str
    planned_min: float
    actual_min: float
    delta_min: float
    delta_pct: float | None


def tm_section_variance(
    planned: Sequence[float],
    actual: Sequence[float],
) -> float | None:
    """Mean absolute percent deviation of actual vs planned section durations.

    N/A when there is no plan (empty planned list). Extra actuals are ignored;
    missing actuals count as 0.
    """
    if not planned:
        return None
    total = 0.0
    n = 0
    for index, plan_min in enumerate(planned):
        if plan_min <= 0:
            continue
        got = float(actual[index]) if index < len(actual) else 0.0
        total += abs(got - plan_min) / plan_min
        n += 1
    if n == 0:
        return None
    return total / n


def planned_vs_actual(
    planned: Sequence[Mapping[str, Any]],
    actual: Sequence[Mapping[str, Any]],
) -> list[SectionRow]:
    """Time-tab rows: Section | Planned | Actual | Δ."""
    by_name = {str(row.get("section") or row.get("name") or ""): row for row in actual}
    rows: list[SectionRow] = []
    for item in planned:
        name = str(item.get("section") or item.get("name") or "")
        plan_min = float(item.get("minutes") or item.get("planned_min") or 0.0)
        match = by_name.get(name) or {}
        got = float(match.get("minutes") or match.get("actual_min") or 0.0)
        delta = got - plan_min
        pct = None if plan_min <= 0 else delta / plan_min
        rows.append(SectionRow(name, plan_min, got, delta, pct))
    return rows


def rehearsal_progress(
    rehearsals: Sequence[Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Progress of each objective across ≥ 2 rehearsals."""
    if len(rehearsals) < 2:
        return {"ready": False, "reason": "need ≥ 2 rehearsals", "objectives": []}
    ids: list[str] = []
    seen: set[str] = set()
    for rehearsal in rehearsals:
        for row in rehearsal:
            oid = str(row.get("objective_id") or row.get("id") or "")
            if oid and oid not in seen:
                seen.add(oid)
                ids.append(oid)
    objectives: list[dict[str, Any]] = []
    for oid in ids:
        history = []
        for rehearsal in rehearsals:
            match = next(
                (
                    row
                    for row in rehearsal
                    if str(row.get("objective_id") or row.get("id") or "") == oid
                ),
                None,
            )
            history.append(
                {
                    "status": (match or {}).get("status") or "na",
                    "score": (match or {}).get("score"),
                }
            )
        objectives.append({"objective_id": oid, "history": history})
    return {"ready": True, "rehearsal_count": len(rehearsals), "objectives": objectives}


def link_owned(*, session_user_id: str, plan_user_id: str | None) -> bool:
    """True only when the plan exists and is owned by the session user."""
    return plan_user_id is not None and str(session_user_id) == str(plan_user_id)
