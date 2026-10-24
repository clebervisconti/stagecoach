"""Admin views. User administration and existing ops routes require role=admin."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.account_deletion import process_due_deletions
from app.admin_users import (
    create_user,
    delete_user,
    get_active_user,
    list_users,
    reset_user_password,
    revoke_sessions,
    update_user,
    user_view,
)
from app.auth import get_current_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.job_step import JobStep
from app.models.session import Session as TalkSession
from app.models.user import User
from app.observability import error_tracking_status, summarize_steps
from app.roles import ROLE_ADMIN

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if (user.role or "") != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host
    return "unknown"


class CreateUserBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = None
    temp_password: Optional[str] = Field(None, max_length=200)
    online_modes: bool = False


class UpdateUserBody(BaseModel):
    role: Optional[str] = None
    disabled: Optional[bool] = None
    online_modes: Optional[bool] = None
    name: Optional[str] = Field(None, max_length=255)


class ResetPasswordBody(BaseModel):
    temp_password: Optional[str] = Field(None, max_length=200)


@router.get("/users")
def admin_list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    q: str = Query("", max_length=200),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    rows, total = list_users(db, q=q, limit=limit, offset=offset)
    return {"users": [user_view(row) for row in rows], "total": total}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def admin_create_user(
    body: CreateUserBody,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user, raw = create_user(
        db,
        admin,
        email=body.email,
        name=body.name,
        role=body.role,
        temp_password=body.temp_password,
        online_modes=body.online_modes,
        ip=_client_ip(request),
    )
    return {**user_view(user), "temporary_password": raw}


@router.patch("/users/{user_id}")
def admin_update_user(
    user_id: str,
    body: UpdateUserBody,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = get_active_user(db, user_id)
    updated = update_user(
        db,
        admin,
        user,
        role=body.role,
        disabled=body.disabled,
        online_modes=body.online_modes,
        name=body.name,
        ip=_client_ip(request),
    )
    return user_view(updated)


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: str,
    request: Request,
    body: ResetPasswordBody | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = get_active_user(db, user_id)
    raw = reset_user_password(
        db,
        admin,
        user,
        temp_password=body.temp_password if body else None,
        ip=_client_ip(request),
    )
    return {**user_view(user), "temporary_password": raw}


@router.post("/users/{user_id}/revoke-sessions")
def admin_revoke_sessions(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = get_active_user(db, user_id)
    version = revoke_sessions(db, admin, user, ip=_client_ip(request))
    return {"id": str(user.id), "session_version": version}


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = get_active_user(db, user_id)
    delete_user(db, admin, user, ip=_client_ip(request))
    return {"status": "deleted"}


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


@router.post("/account-deletions/finalize")
def finalize_account_deletions(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Hard-delete accounts whose 7-day grace has elapsed. Counts only."""
    finalized = process_due_deletions(db, now=datetime.utcnow())
    return {"count": len(finalized), "finalized": finalized, "pii": False}
