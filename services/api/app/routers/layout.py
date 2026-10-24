"""Layout review API (spec §8.4). Accept, edit, and re-analyse."""

from __future__ import annotations

import json
import shutil
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
from app.layout_schema import (
    LayoutPutBody,
    confirmed_document,
    count_edits,
    reanalyse_seed,
    validate_timeline,
    validate_window_inside,
)
from app.models.analysis_job import AnalysisJob
from app.models.job_step import JobStep
from app.models.session import Session as SessionModel
from app.models.session_layout import SessionLayout
from app.models.user import User
from app.rate_limit import consume
from app.retention import normalize_retention_policy
from app.routers.sessions import MEDIA_ROOT, REDIS_URL, _owned_session, sign_playback, verify_playback

router = APIRouter(prefix="/sessions", tags=["layout"])

PREVIEW_TTL_S = 15 * 60


class LayoutAcceptBody(BaseModel):
    audio_only: bool = False


LAYOUT_WRITE_RATE = 0.2
LAYOUT_WRITE_BURST = 8


def layout_write_allowed(store, user_id: str, *, now: Optional[float] = None) -> tuple[bool, float]:
    """Tighter bucket on layout writes. The global /api/v1 bucket still applies."""
    return consume(
        store,
        f"rl:layout:{user_id}",
        rate_per_sec=LAYOUT_WRITE_RATE,
        burst=LAYOUT_WRITE_BURST,
        now=now,
    )


def _latest_job(session: SessionModel, db: Session) -> AnalysisJob:
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.session_id == session.id)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
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


def reference_job_media(src: Path, dest: Path) -> None:
    """Point a new job at the previous ingest files. Transcript stays on the old job for reuse."""
    dest.mkdir(parents=True, exist_ok=True)
    ingest = src / "ingest.json"
    if ingest.is_file():
        shutil.copyfile(ingest, dest / "ingest.json")
    layout_file = src / "layout.json"
    if layout_file.is_file():
        shutil.copyfile(layout_file, dest / "layout.json")
    poster = src / "poster.jpg"
    poster_link = dest / "poster.jpg"
    if poster.is_file() and not poster_link.exists():
        poster_link.symlink_to(poster.resolve())
    preview = src / "layout_preview"
    preview_link = dest / "layout_preview"
    if preview.is_dir() and not preview_link.exists():
        preview_link.symlink_to(preview.resolve(), target_is_directory=True)


def _enforce_layout_write(user_id: str) -> None:
    try:
        import redis

        store = redis.from_url(REDIS_URL)
        allowed, retry = layout_write_allowed(store, user_id)
    except Exception:
        return
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many layout updates. Try again shortly.",
            headers={"Retry-After": str(max(1, int(retry) + 1))},
        )


def _enqueue_analysis(
    session: SessionModel,
    job: AnalysisJob,
    current_user: User,
    db: Session,
    *,
    audio_only: bool,
    analysis_window: Optional[dict] = None,
    layout_path: Optional[str] = None,
) -> None:
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
            "analysis_window": analysis_window,
            "layout_path": layout_path,
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
    window = None
    if row and row.detected:
        window = (row.detected or {}).get("analysis_window")
    _enqueue_analysis(
        session,
        job,
        current_user,
        db,
        audio_only=audio_only,
        analysis_window=window,
        layout_path=str(_job_dir(session, job) / "layout.json"),
    )
    return {"status": "processing", "layout_version": row.version if row else 1, "audio_only": audio_only}


def _duration_s(detected: dict[str, Any], segments: list) -> float:
    frame = detected.get("frame") or {}
    duration = float(frame.get("duration_s") or 0)
    if duration <= 0 and segments:
        duration = max(float(segment.t_end) for segment in segments)
    return duration


def _reject_layout(exc: Exception) -> None:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.put("/{session_id}/layout", status_code=status.HTTP_202_ACCEPTED)
async def put_layout(
    session_id: str,
    body: LayoutPutBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _enforce_layout_write(str(current_user.id))
    session = _owned_session(session_id, current_user, db)
    job = _latest_job(session, db)
    row = (
        db.query(SessionLayout)
        .filter(SessionLayout.session_id == session.id, SessionLayout.job_id == job.id)
        .order_by(SessionLayout.created_at.desc())
        .first()
    )
    detected: dict[str, Any] = {}
    current_version = 1
    if row:
        detected = dict(row.detected or {})
        current_version = int(row.version or 1)
    else:
        layout_file = _job_dir(session, job) / "layout.json"
        if layout_file.is_file():
            detected = json.loads(layout_file.read_text())
            current_version = int(detected.get("version") or 1)
    if body.version != current_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="layout version conflict")
    try:
        duration = _duration_s(detected, body.segments)
        validate_timeline(body.segments, duration)
        validate_window_inside(body.analysis_window, duration)
    except ValueError as exc:
        _reject_layout(exc)
    edits = count_edits(detected or {"segments": []}, body)
    layout_status = "confirmed" if edits == 0 else "corrected"
    version = current_version + 1
    document = confirmed_document(detected, body, version=version, status=layout_status)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        row = SessionLayout(
            session_id=session.id,
            job_id=job.id,
            version=version,
            status=layout_status,
            detector_version=str(document.get("detector_version") or "1.0.0"),
            confidence=float(document.get("confidence") or 1),
            detected=detected or document,
            confirmed=document,
            edit_count=edits,
            confirmed_at=now,
        )
        db.add(row)
    else:
        row.version = version
        row.status = layout_status
        row.confirmed = document
        row.edit_count = edits
        row.confirmed_at = now
        row.confidence = float(document.get("confidence") or row.confidence or 1)
    window = document.get("analysis_window")
    session.analysis_window = window
    session.status = "processing"
    layout_file = _job_dir(session, job) / "layout.json"
    layout_file.parent.mkdir(parents=True, exist_ok=True)
    layout_file.write_text(json.dumps(document, indent=2) + "\n")
    db.commit()
    _enqueue_analysis(
        session,
        job,
        current_user,
        db,
        audio_only=False,
        analysis_window=window,
        layout_path=str(layout_file),
    )
    return {"status": "processing", "layout_version": version, "edit_count": edits}


@router.post("/{session_id}/reanalyse-layout", status_code=status.HTTP_202_ACCEPTED)
async def reanalyse_layout(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """F6: new job, same ingest files, layout review reopens. ASR waits until save."""
    _enforce_layout_write(str(current_user.id))
    session = _owned_session(session_id, current_user, db)
    job = _latest_job(session, db)
    row = _latest_layout(session, db)
    source = _job_dir(session, job)
    if not (source / "ingest.json").is_file():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recording is not ready to re-analyse")
    seed = reanalyse_seed(dict(row.confirmed or row.detected or {}))
    new_job = AnalysisJob(
        session_id=session.id,
        scoring_config_version=job.scoring_config_version,
        pipeline_version=job.pipeline_version,
        status="pending",
    )
    db.add(new_job)
    db.flush()
    destination = _job_dir(session, new_job)
    reference_job_media(source, destination)
    (destination / "layout.json").write_text(json.dumps(seed, indent=2) + "\n")
    new_row = SessionLayout(
        session_id=session.id,
        job_id=new_job.id,
        version=1,
        status="detected",
        detector_version=row.detector_version,
        confidence=row.confidence,
        detected=seed,
        confirmed=None,
        edit_count=0,
    )
    db.add(new_row)
    session.status = "layout_review"
    db.commit()
    return {"status": "layout_review", "job_id": str(new_job.id), "layout_version": 1}
