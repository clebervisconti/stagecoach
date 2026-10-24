"""Resumable chunked uploads for one owned session. See ADR-085."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.chunk_upload import (
    CHUNK_BYTES,
    MAX_CHUNK_BYTES,
    UploadRejected,
    assemble_upload,
    create_store,
    declare_upload,
    delete_upload,
    exclusive,
    load_meta,
    status_of,
    valid_upload_id,
    write_chunk,
)
from app.database import get_db
from app.models.user import User
from app.online_flags import user_online_modes_enabled
from app.routers import sessions as sessions_mod

router = APIRouter(prefix="/sessions", tags=["sessions"])


class UploadCreateBody(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field("", max_length=127)
    size: int = Field(..., ge=1)
    rights_attested: bool = False


def _error(exc: UploadRejected) -> JSONResponse:
    payload: dict = {"detail": exc.detail, "code": exc.code}
    payload.update(exc.extra)
    return JSONResponse(status_code=exc.status_code, content=payload)


def _parts_root(session) -> Path:
    root = sessions_mod.MEDIA_ROOT.resolve()
    path = (root / str(session.id) / "upload-parts").resolve()
    if not path.is_relative_to(root) or path == root:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session path")
    return path


def _upload_dir(session, upload_id: str) -> Path:
    if not valid_upload_id(upload_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload id")
    base = _parts_root(session)
    path = (base / upload_id).resolve()
    if not path.is_relative_to(base):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload id")
    return path


def _open_session(session_id: str, user: User, db: Session, *, writing: bool):
    session = sessions_mod._owned_session(session_id, user, db)
    delivery_mode = getattr(session, "delivery_mode", "stage") or "stage"
    if delivery_mode != "stage" and not user_online_modes_enabled(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Online modes are not enabled")
    if writing and session.status not in {"created", "failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already uploaded")
    return session


async def _read_capped(request: Request) -> bytes:
    header = request.headers.get("content-length")
    if header is not None:
        try:
            declared = int(header)
        except ValueError as exc:
            raise UploadRejected(400, "bad_chunk", "Content-Length is not a number") from exc
        if declared < 0:
            raise UploadRejected(400, "bad_chunk", "Content-Length is not a number")
        if declared > MAX_CHUNK_BYTES:
            raise UploadRejected(
                413,
                "chunk_too_large",
                "This request is larger than one upload chunk.",
                limit_bytes=MAX_CHUNK_BYTES,
            )
    data = await request.body()
    if len(data) > MAX_CHUNK_BYTES:
        raise UploadRejected(
            413,
            "chunk_too_large",
            "This request is larger than one upload chunk.",
            limit_bytes=MAX_CHUNK_BYTES,
        )
    if not data:
        raise UploadRejected(400, "bad_chunk", "Chunk body is empty")
    return data


def _with_id(upload_id: str, payload: dict) -> dict:
    body = dict(payload)
    body["upload_id"] = upload_id
    return body


@router.post("/{session_id}/uploads", status_code=status.HTTP_201_CREATED)
async def create_chunk_upload(
    session_id: str,
    body: UploadCreateBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Open a chunked upload. Each later chunk stays under the proxy body cap."""
    session = _open_session(session_id, current_user, db, writing=True)
    try:
        meta = declare_upload(
            filename=body.filename,
            content_type=body.content_type,
            size=body.size,
            max_bytes=sessions_mod.MAX_FILE_SIZE,
            allowed_extensions=sessions_mod.ALLOWED_EXTENSIONS,
            allowed_content_types=sessions_mod.ALLOWED_CONTENT_TYPES,
            chunk_bytes=CHUNK_BYTES,
        )
    except UploadRejected as exc:
        return _error(exc)
    sessions_mod.attest_rights(session, current_user, db, body.rights_attested)
    db.commit()
    upload_id = uuid.uuid4().hex
    directory = _upload_dir(session, upload_id)
    create_store(directory, meta)
    return _with_id(upload_id, status_of(directory))


@router.get("/{session_id}/uploads/{upload_id}")
async def get_chunk_upload(
    session_id: str,
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _open_session(session_id, current_user, db, writing=False)
    if session.status not in {"created", "failed"}:
        return {
            "upload_id": upload_id,
            "complete": True,
            "already": True,
            "status": session.status,
            "received": [],
            "missing": [],
        }
    directory = _upload_dir(session, upload_id)
    try:
        return _with_id(upload_id, status_of(directory))
    except UploadRejected as exc:
        return _error(exc)


@router.put("/{session_id}/uploads/{upload_id}/chunks/{index}")
async def put_chunk(
    session_id: str,
    upload_id: str,
    index: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _open_session(session_id, current_user, db, writing=True)
    directory = _upload_dir(session, upload_id)
    try:
        if not (directory / "meta.json").is_file():
            raise UploadRejected(404, "not_found", "Upload not found")
        data = await _read_capped(request)
        with exclusive(directory):
            stored = write_chunk(directory, index, data)
    except UploadRejected as exc:
        return _error(exc)
    return _with_id(upload_id, stored)


@router.post("/{session_id}/uploads/{upload_id}/complete", status_code=status.HTTP_202_ACCEPTED)
async def complete_chunk_upload(
    session_id: str,
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _open_session(session_id, current_user, db, writing=False)
    if session.status not in {"created", "failed"}:
        return {"session_id": str(session.id), "status": session.status, "already": True}
    directory = _upload_dir(session, upload_id)
    if not (directory / "meta.json").is_file():
        return _error(UploadRejected(404, "not_found", "Upload not found"))
    try:
        meta = load_meta(directory)
    except UploadRejected as exc:
        return _error(exc)
    upload_dir = (sessions_mod.MEDIA_ROOT / str(session.id) / "upload").resolve()
    if not upload_dir.is_relative_to(sessions_mod.MEDIA_ROOT.resolve()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session path")
    upload_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = upload_dir / f"{uuid.uuid4().hex}{meta['extension']}"
    try:
        with exclusive(directory):
            db.refresh(session)
            if session.status not in {"created", "failed"}:
                return {"session_id": str(session.id), "status": session.status, "already": True}
            assembled = assemble_upload(directory, destination)
            result = sessions_mod.finalize_stored_upload(
                session=session,
                current_user=current_user,
                db=db,
                stored_path=destination,
                total=assembled["size"],
                digest_hex=assembled["sha256"],
                content_type=assembled["content_type"],
                extension=assembled["extension"],
            )
            delete_upload(directory)
            return result
    except UploadRejected as exc:
        return _error(exc)
    except HTTPException as exc:
        destination.unlink(missing_ok=True)
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            delete_upload(directory)
        raise
    except Exception:
        destination.unlink(missing_ok=True)
        raise
