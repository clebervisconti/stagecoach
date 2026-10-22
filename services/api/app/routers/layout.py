"""Layout review API (spec §8.4). Read-only accept / audio-only in O1."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.consents.store import snapshot_for_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.job_step import JobStep
from app.models.session import Session as SessionModel
from app.models.session_layout import SessionLayout
from app.models.user import User
from app.retention import normalize_retention_policy
from app.routers.sessions import MEDIA_ROOT, REDIS_URL, _owned_session, sign_playback, verify_playback

router = APIRouter(prefix="/sessions", tags=["layout"])

PREVIEW_TTL_S = 15 * 60


class LayoutAcceptBody(BaseModel):
    audio_only: bool = False


def _latest_job(session: SessionModel, db: Session) -> AnalysisJob:
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session.id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis job")
    return job


def _latest_layout(session: SessionModel, db: Session) -> SessionLayout:
    row = (
        db.query(SessionLayout)
        .filter(SessionLayout.session_id == session.id)
        .order_by(SessionLayout.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout is not ready")
    return row


def _job_dir(session: SessionModel, job: AnalysisJob) -> Path:
    return (MEDIA_ROOT / str(session.id) / str(job.id)).resolve()


def _layout_payload(row: SessionLayout) -> dict[str, Any]:
    return dict(row.confirmed or row.detected or {})


def _preview_url(session_id: str, index: int) -> str:
    expires = int(time.time()) + PREVIEW_TTL_S
    sig = sign_playback(f"{session_id}:layout:{index}", expires)
    return f"/api/v1/sessions/{session_id}/layout/preview/{index}?exp={expires}&sig={sig}"


def _view(session: SessionModel, job: AnalysisJob, row: SessionLayout) -> dict[str, Any]:
    payload = _layout_payload(row)
    frame = payload.get("frame") or {}
    segments = []
    for index, segment in enumerate(payload.get("segments") or []):
        segments.append(
            {
                **segment,
                "index": segment.get("index", index),
                "preview_url": _preview_url(str(session.id), index),
            }
        )
    return {
        "session_id": str(session.id),
        "job_id": str(job.id),
        "version": row.version,
        "status": row.status,
        "confidence": row.confidence,
        "detector_version": row.detector_version,
        "frame": frame,
        "analysis_window": payload.get("analysis_window"),
        "review_reason": payload.get("review_reason"),
        "preview_t": payload.get("preview_t"),
        "auto_confirmed": row.status == "auto_confirmed",
        "segments": segments,
    }


@router.get("/{session_id}/layout")
async def get_layout(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    job = _latest_job(session, db)
    try:
        row = _latest_layout(session, db)
    except HTTPException:
        layout_file = _job_dir(session, job) / "layout.json"
        if not layout_file.is_file():
            raise
        payload = json.loads(layout_file.read_text())
        fake = SessionLayout(
            session_id=session.id,
            job_id=job.id,
            version=int(payload.get("version") or 1),
            status=str(payload.get("status") or "detected"),
            detector_version=str(payload.get("detector_version") or "1.0.0"),
            confidence=float(payload.get("confidence") or 0),
            detected=payload,
        )
        return _view(session, job, fake)
    return _view(session, job, row)


@router.get("/{session_id}/layout/preview/{index}")
async def get_layout_preview(
    session_id: str,
    index: int,
    exp: int = Query(...),
    sig: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    if exp < int(time.time()) or not verify_playback(f"{session_id}:layout:{index}", exp, sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Preview link expired")
    job = _latest_job(session, db)
    preview = _job_dir(session, job) / "layout_preview" / f"segment_{index:03d}.jpg"
    if not preview.is_file():
        poster = _job_dir(session, job) / "poster.jpg"
        if poster.is_file():
            preview = poster
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview is not ready")
    return FileResponse(
        preview,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{session_id}/poster")
async def get_poster(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    job = _latest_job(session, db)
    poster = _job_dir(session, job) / "poster.jpg"
    if not poster.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster is not ready")
    return FileResponse(poster, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


def _enqueue_analysis(session: SessionModel, job: AnalysisJob, current_user: User, db: Session, *, audio_only: bool) -> None:
    session_dir = MEDIA_ROOT / str(session.id)
    output_dir = session_dir / str(job.id)
    upload_dir = session_dir / "upload"
    originals = sorted(upload_dir.glob("*")) if upload_dir.is_dir() else []
    input_path = str(originals[0]) if originals else str(output_dir / "analysis.mp4")
    celery = Celery("stagecoach-api", broker=REDIS_URL, backend=REDIS_URL)
    celery.send_task(
        "tasks.run_mvp_analysis",
        kwargs={
            "job_id": str(job.id),
            "session_id": str(session.id),
            "input_path": input_path,
            "output_dir": str(output_dir),
            "context_type": session.context_type,
            "language": session.language,
            "slot_min": session.slot_min,
            "consents": snapshot_for_user(db, current_user.id),
            "camera_setup": session.camera_setup,
            "accessibility_profile": current_user.accessibility_profile or {},
            "retention_policy": normalize_retention_policy(getattr(current_user, "retention_policy", None)),
            "llm_settings": getattr(current_user, "llm_settings", None) or {},
            "qa_in_slot": bool(session.qa_in_slot),
            "audience_desc": session.audience_desc,
            "delivery_mode": session.delivery_mode,
            "source_kind": session.source_kind,
            "skip_ingest": True,
            "audio_only_chosen": audio_only,
        },
        queue="cpu",
    )


@router.post("/{session_id}/layout/accept", status_code=status.HTTP_202_ACCEPTED)
async def accept_layout(
    session_id: str,
    body: LayoutAcceptBody | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, current_user, db)
    job = _latest_job(session, db)
    audio_only = bool(body.audio_only) if body else False
    row = (
        db.query(SessionLayout)
        .filter(SessionLayout.session_id == session.id, SessionLayout.job_id == job.id)
        .order_by(SessionLayout.created_at.desc())
        .first()
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row:
        row.status = "confirmed"
        row.confirmed = row.detected
        row.edit_count = 0
        row.confirmed_at = now
        if row.detected:
            detected = dict(row.detected)
            detected["status"] = "confirmed"
            layout_file = _job_dir(session, job) / "layout.json"
            layout_file.write_text(json.dumps(detected, indent=2) + "\n")
    session.status = "processing"
    db.commit()
    _enqueue_analysis(session, job, current_user, db, audio_only=audio_only)
    return {"status": "processing", "layout_version": row.version if row else 1, "audio_only": audio_only}
