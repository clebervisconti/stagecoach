"""Upload quotas. The in-memory stand-in has no join. A real database error must surface."""

from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.models.user import User
from app.quotas import usage_snapshot
from tests.memory_db import MemoryDB


class _BrokenQuery:
    def join(self, *_args: object, **_kwargs: object) -> "_BrokenQuery":
        raise RuntimeError("postgres unavailable")

    def filter(self, *_args: object, **_kwargs: object) -> "_BrokenQuery":
        return self

    def scalar(self) -> int:
        return 0


class _BrokenDB:
    def query(self, *_args: object, **_kwargs: object) -> _BrokenQuery:
        return _BrokenQuery()


def _user() -> User:
    return User(id=uuid.uuid4(), email="quota@example.com")


def test_memory_standin_counts_stored_media_as_zero():
    snap = usage_snapshot(MemoryDB(), _user())
    assert snap == {"storage_bytes": 0, "active_jobs": 0, "monthly_seconds": 0}


def test_database_error_propagates_instead_of_allowing_the_upload():
    with pytest.raises(RuntimeError, match="postgres unavailable"):
        usage_snapshot(_BrokenDB(), _user())
