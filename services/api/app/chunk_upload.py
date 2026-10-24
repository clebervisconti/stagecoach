"""Chunked recording uploads that stay under a reverse-proxy body cap.

Cloudflare rejects a proxied request larger than 100 MB on Free and Pro plans
(200 MB on Business). The browser sends 8 MiB chunks. The API assembles them
on the media volume. See ADR-085.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import fcntl

PRODUCT_MAX_BYTES = 2 * 1024 * 1024 * 1024
CHUNK_BYTES = 8 * 1024 * 1024
MAX_CHUNK_BYTES = 32 * 1024 * 1024
PROXY_BODY_CAP_BYTES = 100 * 1024 * 1024
_EXTENSION = re.compile(r"^\.[a-z0-9]{1,8}$")
_UPLOAD_ID = re.compile(r"^[a-f0-9]{32}$")


class UploadRejected(Exception):
    """A chunk upload the client can classify without guessing."""

    def __init__(self, status_code: int, code: str, detail: str, **extra: object) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.extra = extra


def resolve_max_upload_bytes(
    raw: str | None,
    product_max: int = PRODUCT_MAX_BYTES,
) -> tuple[int, int | None]:
    """Return ``(effective, ignored_low_value)``.

    A configured cap below the product limit is the 80 MiB production default
    that rejected real webinars. The effective limit stays at the product max.
    """
    if raw is None or str(raw).strip() == "":
        return product_max, None
    configured = int(str(raw).strip())
    if configured < 1:
        raise ValueError("MAX_UPLOAD_BYTES must be positive")
    if configured < product_max:
        return product_max, configured
    return configured, None


def normalize_chunk_bytes(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > MAX_CHUNK_BYTES:
        raise UploadRejected(500, "bad_config", "Chunk size is not proxy-safe")
    return value


def declare_upload(
    *,
    filename: str,
    content_type: str,
    size: int,
    max_bytes: int,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
    chunk_bytes: int = CHUNK_BYTES,
) -> dict:
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise UploadRejected(400, "empty", "Uploaded file is empty")
    if size > max_bytes:
        raise UploadRejected(
            413,
            "file_too_large",
            "This file is larger than the upload limit. Trim it or export at 720p.",
            limit_bytes=max_bytes,
            size_bytes=size,
        )
    chunk_bytes = normalize_chunk_bytes(chunk_bytes)
    safe_name = Path(filename or "").name[:200]
    extension = Path(safe_name).suffix.casefold()
    if extension not in allowed_extensions or not _EXTENSION.match(extension):
        raise UploadRejected(415, "unsupported_type", "Unsupported file type")
    media_type = (content_type or "").split(";", 1)[0].strip().casefold()
    if media_type and media_type not in allowed_content_types:
        raise UploadRejected(415, "unsupported_type", "Unsupported content type")
    if not media_type:
        media_type = "application/octet-stream"
    return {
        "filename": safe_name or f"recording{extension}",
        "content_type": media_type,
        "extension": extension,
        "size": size,
        "chunk_bytes": chunk_bytes,
    }


def valid_upload_id(upload_id: str) -> bool:
    return bool(_UPLOAD_ID.fullmatch(upload_id or ""))


def chunk_count(meta: dict) -> int:
    size = int(meta["size"])
    chunk_bytes = int(meta["chunk_bytes"])
    return (size + chunk_bytes - 1) // chunk_bytes


def expected_chunk_length(meta: dict, index: int) -> int:
    count = chunk_count(meta)
    if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= count:
        raise UploadRejected(400, "bad_chunk", "Chunk index is outside the file")
    start = index * int(meta["chunk_bytes"])
    remaining = int(meta["size"]) - start
    return min(int(meta["chunk_bytes"]), remaining)


def create_store(directory: Path, meta: dict) -> None:
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    chunks = directory / "chunks"
    chunks.mkdir(mode=0o700)
    os.chmod(chunks, 0o700)
    payload = json.dumps(meta, separators=(",", ":")).encode()
    target = directory / "meta.json"
    target.write_bytes(payload)
    os.chmod(target, 0o600)


def load_meta(directory: Path) -> dict:
    path = directory / "meta.json"
    if not path.is_file():
        raise UploadRejected(404, "not_found", "Upload not found")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadRejected(400, "bad_upload", "Upload metadata is unreadable") from exc
    if not isinstance(raw, dict):
        raise UploadRejected(400, "bad_upload", "Upload metadata is unreadable")
    try:
        size = int(raw["size"])
        chunk_bytes = normalize_chunk_bytes(int(raw["chunk_bytes"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise UploadRejected(400, "bad_upload", "Upload metadata is unreadable") from exc
    extension = str(raw.get("extension") or "")
    if size < 1 or not _EXTENSION.match(extension):
        raise UploadRejected(400, "bad_upload", "Upload metadata is unreadable")
    filename = str(raw.get("filename") or f"recording{extension}")[:200]
    content_type = str(raw.get("content_type") or "application/octet-stream")[:127]
    return {
        "filename": filename,
        "content_type": content_type,
        "extension": extension,
        "size": size,
        "chunk_bytes": chunk_bytes,
    }


def _chunk_path(directory: Path, index: int) -> Path:
    return directory / "chunks" / f"{index:08d}.part"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def status_of(directory: Path) -> dict:
    meta = load_meta(directory)
    received: list[int] = []
    missing: list[int] = []
    for index in range(chunk_count(meta)):
        part = _chunk_path(directory, index)
        expected = expected_chunk_length(meta, index)
        if part.is_file() and part.stat().st_size == expected:
            received.append(index)
        else:
            missing.append(index)
    return {
        "size": meta["size"],
        "chunk_bytes": meta["chunk_bytes"],
        "received": received,
        "missing": missing,
        "complete": not missing,
        "extension": meta["extension"],
        "content_type": meta["content_type"],
        "filename": meta["filename"],
    }


def write_chunk(directory: Path, index: int, data: bytes) -> dict:
    if not isinstance(data, (bytes, bytearray)):
        raise UploadRejected(400, "bad_chunk", "Chunk body is empty")
    payload = bytes(data)
    if len(payload) > MAX_CHUNK_BYTES:
        raise UploadRejected(
            413,
            "chunk_too_large",
            "This request is larger than one upload chunk.",
            limit_bytes=MAX_CHUNK_BYTES,
        )
    meta = load_meta(directory)
    expected = expected_chunk_length(meta, index)
    if len(payload) != expected:
        raise UploadRejected(
            400,
            "bad_chunk",
            "Chunk length does not match",
            expected_bytes=expected,
            got_bytes=len(payload),
        )
    part = _chunk_path(directory, index)
    incoming = _sha256(payload)
    if part.is_file():
        if part.stat().st_size == expected and _file_sha256(part) == incoming:
            return status_of(directory)
        raise UploadRejected(409, "chunk_conflict", "Chunk was already stored with different bytes")
    partial = part.with_name(part.name + ".partial")
    try:
        with partial.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, part)
        os.chmod(part, 0o600)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return status_of(directory)


def assemble_upload(directory: Path, destination: Path) -> dict:
    """Concatenate complete chunks onto ``destination`` and return the digest.

    Chunk files stay in place until the caller deletes the upload directory,
    so a crash while writing the original can resume.
    """
    meta = load_meta(directory)
    current = status_of(directory)
    if current["missing"]:
        raise UploadRejected(
            409,
            "incomplete",
            "Upload is incomplete",
            missing=current["missing"],
        )
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    digest = hashlib.sha256()
    total = 0
    try:
        with destination.open("xb") as handle:
            for index in range(chunk_count(meta)):
                part = _chunk_path(directory, index)
                with part.open("rb") as source:
                    while block := source.read(1024 * 1024):
                        digest.update(block)
                        handle.write(block)
                        total += len(block)
            handle.flush()
            os.fsync(handle.fileno())
        if total != meta["size"]:
            raise UploadRejected(400, "size_mismatch", "Assembled size does not match the declared size")
        os.chmod(destination, 0o600)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    assembled = dict(meta)
    assembled["sha256"] = digest.hexdigest()
    assembled["size"] = total
    return assembled


def delete_upload(directory: Path) -> None:
    if directory.exists():
        shutil.rmtree(directory)


@contextmanager
def exclusive(directory: Path) -> Iterator[None]:
    """Serialize writers for one upload. flock is not re-entrant; do not nest it."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    handle = (directory / ".lock").open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
