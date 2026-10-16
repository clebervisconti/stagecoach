"""GET /trends (issue #64)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.category_score import CategoryScore
from app.models.metric_value import MetricValue
from app.models.overall_score import OverallScore
from app.models.session import Session as SessionModel
from app.models.user import User
from app.trends_service import build_trends

router = APIRouter(tags=["trends"])


def _latest_job(db: Session, session_id: Any) -> AnalysisJob | None:
    return (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session_id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )


@router.get("/trends")
def get_trends(
    metric: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    context: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.user_id == current_user.id)
        .order_by(SessionModel.created_at.desc())
        .limit(50)
        .all()
    )
    rows: list[dict[str, Any]] = []
    for session in sessions:
        job = _latest_job(db, session.id)
        overall = None
        config_version = None
        categories: dict[str, Any] = {}
        metrics: dict[str, Any] = {}
        if job is not None:
            config_version = job.scoring_config_version
            score_row = db.query(OverallScore).filter(OverallScore.job_id == job.id).first()
            if score_row is not None:
                overall = score_row.overall
                config_version = score_row.config_version or config_version
            for cat in db.query(CategoryScore).filter(CategoryScore.job_id == job.id).all():
                categories[cat.category_id] = cat.score
            for met in db.query(MetricValue).filter(MetricValue.job_id == job.id).all():
                metrics[met.metric_id] = met.raw_value
        rows.append(
            {
                "session_id": str(session.id),
                "title": session.title,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "context_type": session.context_type,
                "language": session.language,
                "config_version": config_version,
                "overall": overall,
                "categories": categories,
                "metrics": metrics,
            }
        )
    return build_trends(
        rows,
        metric=metric,
        category=category,
        context=context,
        language=language,
    )
