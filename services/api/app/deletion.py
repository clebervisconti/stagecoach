"""Hard-delete helpers for sessions (SPEC §10.3, §7.3). Audit records hold counts only."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

logger = logging.getLogger(__name__)

CONTENT_KEYS = {
    "title",
    "transcript",
    "text",
    "quote",
    "summary",
    "body",
    "filename",
    "storage_uri",
    "object_key",
    "keys",
}

MINIO_BUCKET = os.getenv("MINIO_BUCKET", "stagecoach")


class ObjectStore(Protocol):
    def delete_prefix(self, prefix: str) -> int: ...

    def remaining(self, prefix: str) -> int: ...


def session_object_prefix(user_id: UUID | str, session_id: UUID | str) -> str:
    return f"users/{user_id}/sessions/{session_id}/"


def local_session_dir(media_root: Path, session_id: UUID | str) -> Path:
    root = media_root.resolve()
    directory = (root / str(session_id)).resolve()
    if not directory.is_relative_to(root) or directory == root:
        raise ValueError("Invalid session path")
    return directory


def count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.rglob("*") if path.is_file())


def delete_local_prefix(directory: Path, media_root: Path) -> int:
    root = media_root.resolve()
    target = directory.resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError("Refusing to delete outside the session prefix")
    deleted = count_files(target)
    if target.exists():
        shutil.rmtree(target)
    return deleted


def audit_details(*, object_count: int, db_rows: dict[str, int], prefixes: list[str]) -> dict[str, Any]:
    details = {
        "object_count": object_count,
        "db_rows": dict(db_rows),
        "prefixes": list(prefixes),
    }
    assert_no_content(details)
    return details


def assert_no_content(payload: dict[str, Any]) -> None:
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key.lower() in CONTENT_KEYS:
                    raise ValueError(f"audit payload must not contain {key}")
                stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str) and len(item) > 200:
            raise ValueError("audit payload must not contain long content strings")


def ip_hash(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


class NullObjectStore:
    def delete_prefix(self, prefix: str) -> int:
        return 0

    def remaining(self, prefix: str) -> int:
        return 0


class DictObjectStore:
    """In-memory prefix store for tests."""

    def __init__(self, keys: list[str] | None = None) -> None:
        self.keys = set(keys or [])

    def delete_prefix(self, prefix: str) -> int:
        doomed = {key for key in self.keys if key.startswith(prefix)}
        self.keys -= doomed
        return len(doomed)

    def remaining(self, prefix: str) -> int:
        return sum(1 for key in self.keys if key.startswith(prefix))


class S3ObjectStore:
    def __init__(self, client: Any, bucket: str = MINIO_BUCKET) -> None:
        self.client = client
        self.bucket = bucket

    def _list(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            response = self.client.list_objects_v2(**kwargs)
            for item in response.get("Contents") or []:
                key = item.get("Key")
                if key:
                    keys.append(key)
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
        return keys

    def delete_prefix(self, prefix: str) -> int:
        keys = self._list(prefix)
        for offset in range(0, len(keys), 1000):
            chunk = keys[offset : offset + 1000]
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
            )
        return len(keys)

    def remaining(self, prefix: str) -> int:
        return len(self._list(prefix))


def build_object_store() -> ObjectStore:
    endpoint = os.getenv("MINIO_ENDPOINT")
    access = os.getenv("MINIO_ACCESS_KEY")
    secret = os.getenv("MINIO_SECRET_KEY")
    if not endpoint or not access or not secret:
        return NullObjectStore()
    try:
        import boto3
        from botocore.client import Config
    except ImportError:
        logger.info("boto3 is not installed; skipping MinIO prefix delete")
        return NullObjectStore()
    scheme = "" if endpoint.startswith("http") else "http://"
    client = boto3.client(
        "s3",
        endpoint_url=f"{scheme}{endpoint}",
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        config=Config(
            signature_version="s3v4",
            connect_timeout=1,
            read_timeout=2,
            retries={"max_attempts": 0},
        ),
        region_name=os.getenv("MINIO_REGION", "us-east-1"),
    )
    try:
        client.head_bucket(Bucket=MINIO_BUCKET)
    except Exception as exc:
        logger.info("MinIO not reachable (%s); local prefix delete only", type(exc).__name__)
        return NullObjectStore()
    return S3ObjectStore(client)
