"""POST/GET /goals (issue #65)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.goals_service import apply_progress, progress_label, validate_goal
from app.models.analysis_job import AnalysisJob
from app.models.category_score import CategoryScore
from app.models.metric_value import MetricValue
from app.models.session import Session as SessionModel
from app.models.talk_plan import Goal
from app.models.user import User

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalCreate(BaseModel):
    metric_id: Optional[str] = Field(None, max_length=80)
    category_id: Optional[str] = Field(None, max_length=80)
    comparator: str = Field(..., max_length=16)
    target: float


def _latest_job(db: Session, user_id: Any) -> AnalysisJob | None:
    session = (
        db.query(SessionModel)
        .filter(SessionModel.user_id == user_id)
        .order_by(SessionModel.created_at.desc())
        .first()
    )
    if session is None:
        return None
    return (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session.id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )


def _latest_value(db: Session, job: AnalysisJob | None, goal: Goal) -> float | None:
    if job is None:
        return None
    if goal.metric_id:
        row = (
            db.query(MetricValue)
            .filter(MetricValue.job_id == job.id, MetricValue.metric_id == goal.metric_id)
            .first()
        )
        return None if row is None else row.raw_value
    row = (
        db.query(CategoryScore)
        .filter(CategoryScore.job_id == job.id, CategoryScore.category_id == goal.category_id)
        .first()
    )
    return None if row is None or row.score is None else float(row.score)


def _serialize(goal: Goal, latest: float | None) -> dict[str, Any]:
    payload = apply_progress(
        {
            "id": str(goal.id),
            "metric_id": goal.metric_id,
            "category_id": goal.category_id,
            "comparator": goal.comparator,
            "target": goal.target,
            "created_at": goal.created_at.isoformat() if goal.created_at else None,
            "achieved_at": goal.achieved_at.isoformat() if goal.achieved_at else None,
        },
        latest,
    )
    payload["label"] = progress_label(payload)
    return payload


@router.post("", status_code=201)
def create_goal(
    body: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    validate_goal(body.metric_id, body.category_id, body.comparator)
    goal = Goal(
        user_id=current_user.id,
        metric_id=body.metric_id,
        category_id=body.category_id,
        comparator=body.comparator,
        target=body.target,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _serialize(goal, None)


@router.get("")
def list_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    job = _latest_job(db, current_user.id)
    rows = (
        db.query(Goal)
        .filter(Goal.user_id == current_user.id)
        .order_by(Goal.created_at.desc())
        .all()
    )
    goals = []
    for row in rows:
        latest = _latest_value(db, job, row)
        payload = _serialize(row, latest)
        if payload.get("achieved_at") and row.achieved_at is None:
            raw = payload["achieved_at"]
            parsed = datetime.fromisoformat(raw) if isinstance(raw, str) else raw
            if getattr(parsed, "tzinfo", None):
                parsed = parsed.replace(tzinfo=None)
            row.achieved_at = parsed
        goals.append(payload)
    if any(row.achieved_at is not None for row in rows):
        db.commit()
    return {"goals": goals}
