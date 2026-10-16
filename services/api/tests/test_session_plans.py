"""Session ↔ talk-plan link (issue #63). No live database."""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.session_plans import resolve_talk_plan
from app.routers.sessions import SessionCreate


class _Query:
    def __init__(self, plan):
        self._plan = plan

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._plan


class _Db:
    def __init__(self, plan):
        self._plan = plan

    def query(self, _model):
        return _Query(self._plan)


def test_resolve_owned_plan():
    owner = uuid4()
    plan_id = uuid4()
    plan = SimpleNamespace(id=plan_id, user_id=owner)
    assert resolve_talk_plan(_Db(plan), owner, plan_id) is plan


def test_resolve_foreign_or_missing_is_404():
    owner = uuid4()
    other = uuid4()
    plan = SimpleNamespace(id=uuid4(), user_id=owner)
    with pytest.raises(HTTPException) as foreign:
        resolve_talk_plan(_Db(plan), other, plan.id)
    assert foreign.value.status_code == 404
    with pytest.raises(HTTPException) as missing:
        resolve_talk_plan(_Db(None), owner, uuid4())
    assert missing.value.status_code == 404
    assert resolve_talk_plan(_Db(None), owner, None) is None


def test_session_create_accepts_talk_plan_id():
    plan_id = uuid4()
    body = SessionCreate(
        title="Rehearsal 1",
        context_type="exec_briefing",
        language="en",
        camera_setup="to_camera",
        talk_plan_id=plan_id,
    )
    assert body.talk_plan_id == plan_id
