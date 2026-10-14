"""User retention policy mapping (issue #50)."""

import os
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import pytest
from fastapi import HTTPException

from app.retention import (
    AFTER_ANALYSIS,
    DAYS_30,
    DEFAULT_RETENTION_DAYS,
    UNTIL_DELETE,
    UNTIL_DELETE_SENTINEL,
    normalize_retention_policy,
    retention_until_for,
)
from app.routers.users import parse_retention_policy


def test_normalize_defaults_and_rejects_unknown():
    assert normalize_retention_policy(None) == DAYS_30
    assert normalize_retention_policy("until_delete") == UNTIL_DELETE
    with pytest.raises(ValueError):
        normalize_retention_policy("forever")


def test_upload_and_analysis_clock():
    now = datetime(2026, 6, 15, 8, 0, 0)
    assert retention_until_for(DAYS_30, now, "upload") == now + timedelta(days=DEFAULT_RETENTION_DAYS)
    assert retention_until_for(AFTER_ANALYSIS, now, "analysis_complete") == now
    assert retention_until_for(UNTIL_DELETE, now, "upload") == UNTIL_DELETE_SENTINEL


def test_user_router_rejects_unknown_policy():
    with pytest.raises(HTTPException) as exc:
        parse_retention_policy("keep_forever")
    assert exc.value.status_code == 422
    assert parse_retention_policy(None) == DAYS_30
    assert parse_retention_policy("after_analysis") == AFTER_ANALYSIS
