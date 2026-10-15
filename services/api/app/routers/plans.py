"""Talk-plan API (SPEC §7.5 / issue #55)."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.talk_plan import ObjectiveScore, TalkPlan
from app.models.user import User
from app.plans_service import (
    CONTEXT_TYPES,
    apply_regenerate,
    apply_user_edit,
    prep_llm_payload,
    require_owned,
)

router = APIRouter(prefix="/plans", tags=["plans"])
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CONTEXT_PATTERN = "^(" + "|".join(CONTEXT_TYPES) + ")$"
LANG_PATTERN = "^(en|pt-BR)$"


class PlanCreate(BaseModel):
    title: str = Field(..., max_length=255)
    context_type: str = Field(..., pattern=CONTEXT_PATTERN)
    description: Optional[str] = Field(None, max_length=4000)
    audience: Optional[dict[str, Any]] = None
    goal: Optional[str] = None
    slot_min: Optional[int] = Field(None, ge=1, le=180)
    qa_in_slot: bool = False
    qa_min: Optional[int] = Field(None, ge=0, le=120)
    language: str = Field("en", pattern=LANG_PATTERN)
    constraints: Optional[dict[str, Any]] = None
    script_text: Optional[str] = None
    talk_date: Optional[date] = None
    delivery_format: Optional[str] = Field(None, pattern="^(in_person|virtual|hybrid)$")
    known_habits: Optional[list[str]] = None
    must_include: Optional[str] = None


class PlanPatch(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    context_type: Optional[str] = Field(None, pattern=CONTEXT_PATTERN)
    description: Optional[str] = Field(None, max_length=4000)
    audience: Optional[dict[str, Any]] = None
    goal: Optional[str] = None
    slot_min: Optional[int] = Field(None, ge=1, le=180)
    qa_in_slot: Optional[bool] = None
    qa_min: Optional[int] = Field(None, ge=0, le=120)
    language: Optional[str] = Field(None, pattern=LANG_PATTERN)
    constraints: Optional[dict[str, Any]] = None
    script_text: Optional[str] = None
    outputs: Optional[dict[str, Any]] = None
    talk_date: Optional[date] = None
    delivery_format: Optional[str] = Field(None, pattern="^(in_person|virtual|hybrid)$")
    known_habits: Optional[list[str]] = None
    must_include: Optional[str] = None


class PlanRegenerate(BaseModel):
    section: str = "all"
    feedback: str = ""


def _enqueue_prep(plan_id: str, section: str, feedback: str, user: User) -> None:
    celery = Celery("stagecoach-api", broker=REDIS_URL, backend=REDIS_URL)
    celery.send_task(
        "tasks.prep_llm",
        kwargs=prep_llm_payload(
            plan_id,
            section=section,
            feedback=feedback,
            llm_settings=getattr(user, "llm_settings", None) or {},
        ),
        queue="llm",
    )


def _serialize(plan: TalkPlan) -> dict[str, Any]:
    return {
        "id": str(plan.id),
        "title": plan.title,
        "context_type": plan.context_type,
        "description": plan.description,
        "audience": plan.audience,
        "goal": plan.goal,
        "slot_min": plan.slot_min,
        "qa_in_slot": plan.qa_in_slot,
        "qa_min": plan.qa_min,
        "language": plan.language,
        "constraints": plan.constraints,
        "script_text": plan.script_text,
        "outputs": plan.outputs,
        "version": plan.version,
        "edit_history": plan.edit_history or [],
        "status": plan.status,
        "talk_date": plan.talk_date.isoformat() if plan.talk_date else None,
        "delivery_format": plan.delivery_format,
        "known_habits": plan.known_habits,
        "must_include": plan.must_include,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    plan = TalkPlan(
        user_id=current_user.id,
        title=body.title,
        context_type=body.context_type,
        description=body.description,
        audience=body.audience,
        goal=body.goal,
        slot_min=body.slot_min,
        qa_in_slot=body.qa_in_slot,
        qa_min=body.qa_min,
        language=body.language,
        constraints=body.constraints,
        script_text=body.script_text,
        outputs=None,
        version=1,
        edit_history=[],
        status="queued",
        talk_date=body.talk_date,
        delivery_format=body.delivery_format,
        known_habits=body.known_habits,
        must_include=body.must_include,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    _enqueue_prep(str(plan.id), "all", "", current_user)
    return _serialize(plan)


@router.get("")
def list_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        db.query(TalkPlan)
        .filter(TalkPlan.user_id == current_user.id)
        .order_by(TalkPlan.created_at.desc())
        .all()
    )
    return {"plans": [_serialize(row) for row in rows]}


@router.get("/{plan_id}")
def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    plan = db.query(TalkPlan).filter(TalkPlan.id == plan_id).first()
    require_owned(plan, current_user.id)
    return _serialize(plan)


@router.patch("/{plan_id}")
def patch_plan(
    plan_id: UUID,
    body: PlanPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    plan = db.query(TalkPlan).filter(TalkPlan.id == plan_id).first()
    require_owned(plan, current_user.id)
    patch = body.model_dump(exclude_unset=True)
    snapshot = {
        "version": plan.version,
        "edit_history": list(plan.edit_history or []),
    }
    updated = apply_user_edit(snapshot, patch)
    for key, value in patch.items():
        setattr(plan, key, value)
    plan.version = updated["version"]
    plan.edit_history = updated["edit_history"]
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return _serialize(plan)


@router.post("/{plan_id}/regenerate")
def regenerate_plan(
    plan_id: UUID,
    body: PlanRegenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    plan = db.query(TalkPlan).filter(TalkPlan.id == plan_id).first()
    require_owned(plan, current_user.id)
    snapshot = {
        "version": plan.version,
        "edit_history": list(plan.edit_history or []),
    }
    updated = apply_regenerate(snapshot, body.section, body.feedback)
    plan.version = updated["version"]
    plan.edit_history = updated["edit_history"]
    plan.status = "queued"
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    _enqueue_prep(str(plan.id), body.section, body.feedback, current_user)
    return _serialize(plan)


@router.get("/{plan_id}/objectives-scores")
def objective_scores(
    plan_id: UUID,
    session_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    plan = db.query(TalkPlan).filter(TalkPlan.id == plan_id).first()
    require_owned(plan, current_user.id)
    query = db.query(ObjectiveScore).filter(ObjectiveScore.talk_plan_id == plan_id)
    if session_id is not None:
        job_ids = [
            row.id
            for row in db.query(AnalysisJob).filter(AnalysisJob.session_id == session_id).all()
        ]
        if not job_ids:
            return {"scores": []}
        query = query.filter(ObjectiveScore.job_id.in_(job_ids))
    rows = query.all()
    return {
        "scores": [
            {
                "id": str(row.id),
                "job_id": str(row.job_id),
                "objective_id": row.objective_id,
                "status": row.status,
                "score": row.score,
                "evidence_ids": row.evidence_ids,
            }
            for row in rows
        ]
    }
