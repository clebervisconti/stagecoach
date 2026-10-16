"""Link a session to an owned talk plan (issue #63)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.talk_plan import TalkPlan
from app.plans_service import require_owned


def resolve_talk_plan(db: Any, user_id: Any, plan_id: UUID | None) -> TalkPlan | None:
    if plan_id is None:
        return None
    plan = db.query(TalkPlan).filter(TalkPlan.id == plan_id).first()
    require_owned(plan, user_id)
    return plan
