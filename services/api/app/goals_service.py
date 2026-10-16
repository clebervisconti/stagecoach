"""User goals: create, progress, achieved_at (SPEC §7.3 / issue #65)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status

COMPARATORS = ("<", "<=", ">", ">=", "=")


def validate_goal(metric_id: Optional[str], category_id: Optional[str], comparator: str) -> None:
    if bool(metric_id) == bool(category_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one of metric_id or category_id",
        )
    if comparator not in COMPARATORS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid comparator")


def goal_met(value: float | None, comparator: str, target: float) -> bool:
    if value is None:
        return False
    if comparator == "<":
        return value < target
    if comparator == "<=":
        return value <= target
    if comparator == ">":
        return value > target
    if comparator == ">=":
        return value >= target
    return value == target


def apply_progress(
    goal: dict[str, Any],
    latest_value: float | None,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Attach latest_value and set achieved_at once when the target is met."""
    updated = dict(goal)
    updated["latest_value"] = latest_value
    if updated.get("achieved_at"):
        return updated
    if goal_met(latest_value, str(goal.get("comparator") or "="), float(goal.get("target") or 0)):
        stamp = now or datetime.now(timezone.utc)
        if stamp.tzinfo is not None:
            stamp = stamp.replace(tzinfo=None)
        updated["achieved_at"] = stamp.isoformat()
    return updated


def progress_label(goal: dict[str, Any]) -> str:
    key = goal.get("metric_id") or goal.get("category_id") or "goal"
    latest = goal.get("latest_value")
    target = goal.get("target")
    mark = " ✓" if goal.get("achieved_at") else ""
    latest_s = "—" if latest is None else str(latest)
    return f"{key} {goal.get('comparator')} {target}: {latest_s}{mark}"
