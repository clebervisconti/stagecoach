"""PDF export status and download (issue #49, SPEC §7.5)."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/exports", tags=["exports"])

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/data/stagecoach")).resolve()


def _export_dir(export_id: str) -> Path:
    dest = (MEDIA_ROOT / "exports" / export_id).resolve()
    if not dest.is_relative_to(MEDIA_ROOT / "exports"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export not found"
        )
    return dest


def _owned_meta(export_id: str, user: User) -> tuple[Path, dict]:
    dest = _export_dir(export_id)
    meta_path = dest / "meta.json"
    if not meta_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export not found"
        )
    try:
        meta = json.loads(meta_path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Export is unreadable"
        ) from exc
    if str(meta.get("user_id")) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export not found"
        )
    return dest, meta


@router.get("/{export_id}")
async def get_export(
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = db
    dest, meta = _owned_meta(export_id, current_user)
    pdf = dest / "report.pdf"
    ready = meta.get("status") == "ready" and pdf.is_file()
    return {
        "id": meta.get("id") or export_id,
        "status": meta.get("status") or "queued",
        "include_transcript": bool(meta.get("include_transcript")),
        "bytes": pdf.stat().st_size if ready else meta.get("bytes"),
        "download": f"/api/v1/exports/{export_id}/file" if ready else None,
        "error": meta.get("error"),
    }


@router.get("/{export_id}/file")
async def get_export_file(
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = db
    dest, meta = _owned_meta(export_id, current_user)
    pdf = dest / "report.pdf"
    if meta.get("status") != "ready" or not pdf.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Export is not ready"
        )
    return FileResponse(
        pdf, media_type="application/pdf", filename="stagecoach-report.pdf"
    )
