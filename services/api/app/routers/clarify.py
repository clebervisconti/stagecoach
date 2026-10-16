"""POST /plans/{id}/clarify (issue #56)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.talk_plan import TalkPlan
from app.models.user import User
from app.plans_service import require_owned
from app.prep_clarify import run_clarify

router = APIRouter(prefix="/plans", tags=["plans"])


class ClarifyBody(BaseModel):
    skip: bool = False
    description: Optional[str] = Field(None, max_length=4000)


@router.post("/{plan_id}/clarify")
def clarify_plan(
    plan_id: UUID,
    body: ClarifyBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    plan = db.query(TalkPlan).filter(TalkPlan.id == plan_id).first()
    require_owned(plan, current_user.id)
    snapshot = {
        "title": plan.title,
        "context_type": plan.context_type,
        "description": body.description if body.description is not None else plan.description,
        "audience": plan.audience or {},
        "goal": plan.goal,
        "slot_min": plan.slot_min,
        "qa_in_slot": plan.qa_in_slot,
        "qa_min": plan.qa_min,
        "language": plan.language,
    }
    result = run_clarify(snapshot, skip=body.skip)
    merged = result["plan"]
    plan.description = merged.get("description") or plan.description
    plan.goal = merged.get("goal")
    plan.slot_min = merged.get("slot_min")
    plan.qa_in_slot = bool(merged.get("qa_in_slot") or False)
    plan.qa_min = merged.get("qa_min")
    plan.audience = merged.get("audience")
    outputs = dict(plan.outputs or {})
    outputs["clarify"] = {
        "questions": result["questions"],
        "assumptions": result["assumptions"],
        "skipped": result["skipped"],
        "extracted": result["extracted"],
        "prompt_id": result["prompt_id"],
    }
    plan.outputs = outputs
    db.commit()
    db.refresh(plan)
    return {
        "id": str(plan.id),
        "questions": result["questions"],
        "assumptions": result["assumptions"],
        "skipped": result["skipped"],
        "extracted": result["extracted"],
        "plan": {
            "goal": plan.goal,
            "slot_min": plan.slot_min,
            "audience": plan.audience,
        },
    }
