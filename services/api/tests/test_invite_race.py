"""An invite can be spent once, including when two requests arrive together."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.identity_service import consume_token
from app.models.user import AuthToken


class _Result:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def first(self) -> object | None:
        return self._row


class _Query:
    def __init__(self, db: "_RacingDB") -> None:
        self.db = db

    def filter(self, *_clauses: object) -> "_Query":
        return self

    def with_for_update(self) -> "_Query":
        return self

    def first(self) -> AuthToken:
        return self.db.row


class _RacingDB:
    """Applies the unused check under one lock, the way the conditional UPDATE does."""

    def __init__(self, row: AuthToken, racers: int) -> None:
        self.row = row
        self.lock = threading.Lock()
        self.barrier = threading.Barrier(racers)
        self.statements: list[object] = []

    def query(self, _model: type) -> _Query:
        return _Query(self)

    def execute(self, statement: object) -> _Result:
        self.statements.append(statement)
        self.barrier.wait(timeout=2)
        with self.lock:
            if self.row.used_at is not None or self.row.expires_at <= datetime.utcnow():
                return _Result(None)
            self.row.used_at = datetime.utcnow()
            return _Result((self.row.id,))


def _token() -> AuthToken:
    return AuthToken(
        id=uuid.uuid4(),
        user_id=None,
        purpose="invite",
        token_hash="placeholder",
        expires_at=datetime.utcnow() + timedelta(days=1),
        used_at=None,
    )


def test_conditional_update_keeps_one_winner_when_two_consume_together():
    raw = "invite-plain-value"
    db = _RacingDB(_token(), racers=2)
    results: list[str] = []
    errors: list[BaseException] = []

    def spend() -> None:
        try:
            consume_token(db, raw, "invite")
            results.append("spent")
        except HTTPException as exc:
            results.append(f"denied:{exc.status_code}")
        except BaseException as exc:  # pragma: no cover - the test reports it
            errors.append(exc)

    threads = [threading.Thread(target=spend), threading.Thread(target=spend)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert errors == []
    assert sorted(results) == ["denied:400", "spent"]
    sql = str(db.statements[0].compile(dialect=postgresql.dialect()))
    assert "used_at IS NULL" in sql
    assert "expires_at" in sql
    assert "RETURNING" in sql


def test_second_consume_is_rejected_after_the_update():
    raw = "invite-once"
    db = _RacingDB(_token(), racers=1)
    first = consume_token(db, raw, "invite")
    assert first.used_at is not None
    with pytest.raises(HTTPException) as denied:
        consume_token(db, raw, "invite")
    assert denied.value.status_code == 400
