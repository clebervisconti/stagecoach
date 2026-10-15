"""User retention choices and media_assets.retention_until (issue #50, SPEC §10.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

AFTER_ANALYSIS = "after_analysis"
DAYS_30 = "days_30"
UNTIL_DELETE = "until_delete"
RETENTION_POLICIES = (AFTER_ANALYSIS, DAYS_30, UNTIL_DELETE)
DEFAULT_RETENTION_POLICY = DAYS_30
DEFAULT_RETENTION_DAYS = 30
UNTIL_DELETE_SENTINEL = datetime(9999, 12, 31)


def normalize_retention_policy(value: Optional[str]) -> str:
    if value in RETENTION_POLICIES:
        return value
    if value in (None, ""):
        return DEFAULT_RETENTION_POLICY
    raise ValueError(f"Unknown retention_policy: {value}")


def retention_until_for(
    policy: Optional[str],
    now: datetime,
    event: str = "upload",
) -> datetime:
    choice = normalize_retention_policy(policy)
    if event == "ephemeral":
        return now
    if choice == UNTIL_DELETE:
        return UNTIL_DELETE_SENTINEL
    if choice == AFTER_ANALYSIS:
        if event == "analysis_complete":
            return now
        return now + timedelta(days=1)
    return now + timedelta(days=DEFAULT_RETENTION_DAYS)
