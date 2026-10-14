"""Evidence dispute endpoint (SPEC §7.5, §2.3 J1.6)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.evidence_item import EvidenceItem
from app.models.job_step import JobStep
from app.models.session import Session as SessionModel
from app.models.user import User
from app.routers.sessions import MEDIA_ROOT, _safe_artifact_path

router = APIRouter(prefix="/evidence", tags=["evidence"])


class DisputeBody(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


def _owned_evidence(evidence_id: str, user: User, db: Session) -> EvidenceItem:
    jobs = (
        db.query(AnalysisJob)
        .join(SessionModel, SessionModel.id == AnalysisJob.session_id)
        .filter(SessionModel.user_id == user.id)
        .all()
    )
    job_ids = [job.id for job in jobs]
    if not job_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    row = None
    try:
        as_uuid = uuid.UUID(evidence_id)
        row = (
            db.query(EvidenceItem)
            .filter(EvidenceItem.id == as_uuid, EvidenceItem.job_id.in_(job_ids))
            .first()
        )
    except ValueError:
        for job in jobs:
            derived = uuid.uuid5(uuid.NAMESPACE_URL, f"stagecoach:evidence:{job.id}:{evidence_id}")
            row = (
                db.query(EvidenceItem)
                .filter(EvidenceItem.id == derived, EvidenceItem.job_id == job.id)
                .first()
            )
            if row:
                break
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return row


def _mark_json_disputed(path: Path, evidence_key: str, note: str) -> None:
    if not path.is_file():
        return
    payload = json.loads(path.read_text())
    changed = False
    for item in payload.get("evidence") or []:
        if item.get("id") == evidence_key or item.get("id") == str(evidence_key):
            item["user_disputed"] = True
            item["dispute_note"] = note
            changed = True
    if changed:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


@router.post("/{evidence_id}/dispute", status_code=status.HTTP_200_OK)
async def dispute_evidence(
    evidence_id: str,
    body: DisputeBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store a user dispute note. Evidence then shows user_disputed."""
    item = _owned_evidence(evidence_id, current_user, db)
    item.user_disputed = True
    item.dispute_note = body.note
    db.commit()

    job = db.query(AnalysisJob).filter(AnalysisJob.id == item.job_id).first()
    step = (
        db.query(JobStep)
        .filter(JobStep.job_id == item.job_id, JobStep.stage == "report")
        .order_by(JobStep.created_at.desc())
        .first()
    )
    logical_id = None
    if evidence_id.startswith("ev-"):
        logical_id = evidence_id
    if step and step.output_uris:
        for key in ("report", "analysis_result"):
            raw = step.output_uris.get(key)
            if not raw:
                continue
            try:
                path = _safe_artifact_path(raw)
            except HTTPException:
                continue
            if path.is_relative_to(MEDIA_ROOT):
                if logical_id:
                    _mark_json_disputed(path, logical_id, body.note)
                payload = json.loads(path.read_text()) if path.is_file() else {}
                for ev in payload.get("evidence") or []:
                    derived = uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"stagecoach:evidence:{item.job_id}:{ev.get('id')}",
                    )
                    if derived == item.id:
                        _mark_json_disputed(path, ev["id"], body.note)

    return {
        "id": str(item.id),
        "user_disputed": True,
        "dispute_note": item.dispute_note,
        "session_id": str(job.session_id) if job else None,
    }
