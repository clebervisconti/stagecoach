"""Admin observability views. Gated by STAGECOACH_ADMIN_EMAILS."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.job_step import JobStep
from app.models.session import Session as TalkSession
from app.models.user import User
from app.observability import error_tracking_status, is_admin_email, summarize_steps

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin_email(user.email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


@router.get("/analysis-costs")
def analysis_costs(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    session_id: Optional[str] = None,
) -> dict:
    query = db.query(AnalysisJob).order_by(AnalysisJob.created_at.desc())
    if session_id:
        query = query.filter(AnalysisJob.session_id == session_id)
    jobs = query.limit(50).all()
    items = []
    for job in jobs:
        steps = (
            db.query(JobStep)
            .filter(JobStep.job_id == job.id)
            .order_by(JobStep.created_at.asc())
            .all()
        )
        talk = db.query(TalkSession).filter(TalkSession.id == job.session_id).first()
        summary = summarize_steps(
            [
                {
                    "stage": step.stage,
                    "status": step.status,
                    "metrics": step.metrics or {},
                }
                for step in steps
            ]
        )
        items.append(
            {
                "job_id": str(job.id),
                "session_id": str(job.session_id),
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "title": talk.title if talk else None,
                **summary,
            }
        )
    return {
        "items": items,
        "error_tracking": error_tracking_status(),
        "pii": False,
    }
