"""Retention policies, ephemeral cleanup, and the nightly sweeper (issue #50).

SPEC §10.1 / §10.3: originals follow the user choice; audio16k and the analysis
proxy are deleted when the job completes; the sweeper cross-checks
`media_assets.retention_until`. Lifecycle rules in
`infra/object-storage-lifecycle.json` are a backstop, not applied in CI.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

AFTER_ANALYSIS = "after_analysis"
DAYS_30 = "days_30"
UNTIL_DELETE = "until_delete"
RETENTION_POLICIES = (AFTER_ANALYSIS, DAYS_30, UNTIL_DELETE)
DEFAULT_RETENTION_POLICY = DAYS_30
DEFAULT_RETENTION_DAYS = 30
UNTIL_DELETE_SENTINEL = datetime(9999, 12, 31)
EPHEMERAL_KINDS = frozenset({"audio16k", "analysis_proxy"})
SWEEPABLE_KINDS = frozenset({"original", "playback", "audio16k", "analysis_proxy"})
EPHEMERAL_NAMES = {
    "audio16k": "audio16k.wav",
    "analysis_proxy": "analysis.mp4",
}


@dataclass(frozen=True)
class AssetRecord:
    id: str
    kind: str
    storage_uri: str
    retention_until: datetime
    session_id: str = ""


def normalize_retention_policy(value: Optional[str]) -> str:
    if value in RETENTION_POLICIES:
        return value
    if value in (None, ""):
        return DEFAULT_RETENTION_POLICY
    raise ValueError(f"Unknown retention_policy: {value}")


def retention_until_for(
    policy: Optional[str],
    now: datetime,
    event: str = "upload",
) -> datetime:
    """Map a user policy + lifecycle event onto media_assets.retention_until."""
    choice = normalize_retention_policy(policy)
    if event == "ephemeral":
        return now
    if choice == UNTIL_DELETE:
        return UNTIL_DELETE_SENTINEL
    if choice == AFTER_ANALYSIS:
        if event == "analysis_complete":
            return now
        return now + timedelta(days=1)
    if event == "analysis_complete":
        return now + timedelta(days=DEFAULT_RETENTION_DAYS)
    return now + timedelta(days=DEFAULT_RETENTION_DAYS)


def ephemeral_paths(output_dir: Path, ingest_artifacts: Optional[dict[str, Any]] = None) -> list[Path]:
    dest = Path(output_dir)
    artifacts = ingest_artifacts or {}
    paths: list[Path] = []
    audio = artifacts.get("audio16k")
    paths.append(Path(audio) if audio else dest / EPHEMERAL_NAMES["audio16k"])
    analysis = artifacts.get("analysis") or artifacts.get("analysis_proxy")
    paths.append(Path(analysis) if analysis else dest / EPHEMERAL_NAMES["analysis_proxy"])
    return paths


def _safe_unlink(path: Path, media_root: Optional[Path] = None) -> bool:
    target = path.resolve() if path.exists() or path.is_absolute() else path
    if media_root is not None:
        root = media_root.resolve()
        try:
            resolved = path.resolve()
        except OSError:
            return False
        if not resolved.is_relative_to(root) or resolved == root:
            logger.info("refusing to delete path outside media root")
            return False
        target = resolved
    if target.is_file():
        target.unlink()
        return True
    return False


def delete_ephemeral_files(
    output_dir: Path,
    ingest_artifacts: Optional[dict[str, Any]] = None,
    media_root: Optional[Path] = None,
) -> list[str]:
    """Remove audio16k / analysis proxy after the job completes (SPEC §10.1)."""
    removed: list[str] = []
    for path in ephemeral_paths(output_dir, ingest_artifacts):
        kind = "audio16k" if path.name.startswith("audio16k") else "analysis_proxy"
        if _safe_unlink(path, media_root=media_root):
            removed.append(kind)
    return removed


def delete_original_upload(input_path: Path, media_root: Optional[Path] = None) -> bool:
    return _safe_unlink(Path(input_path), media_root=media_root)


def sweep_records(
    records: Iterable[AssetRecord],
    now: datetime,
    *,
    media_root: Optional[Path] = None,
    unlink: Optional[Callable[[Path], bool]] = None,
) -> dict[str, Any]:
    """Delete sweepable assets whose retention_until has passed. Time-travel friendly."""
    removed_ids: list[str] = []
    kinds: dict[str, int] = {}
    deleter = unlink or (lambda path: _safe_unlink(path, media_root=media_root))
    for record in records:
        if record.kind not in SWEEPABLE_KINDS:
            continue
        if record.retention_until > now:
            continue
        path = Path(record.storage_uri)
        deleter(path)
        removed_ids.append(record.id)
        kinds[record.kind] = kinds.get(record.kind, 0) + 1
    return {
        "object_count": len(removed_ids),
        "ids": removed_ids,
        "kinds": kinds,
        "now": now.isoformat(),
    }


def finalize_job_media(
    *,
    output_dir: Path,
    input_path: Path,
    ingest_artifacts: Optional[dict[str, Any]] = None,
    retention_policy: Optional[str] = None,
    now: Optional[datetime] = None,
    media_root: Optional[Path] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """Honor user retention after a terminal job; always drop ephemeral transcodes."""
    clock = now or datetime.utcnow()
    policy = normalize_retention_policy(retention_policy)
    deleted = delete_ephemeral_files(output_dir, ingest_artifacts, media_root=media_root)
    original_deleted = False
    if policy == AFTER_ANALYSIS:
        original_deleted = delete_original_upload(input_path, media_root=media_root)
    persist_job_retention(
        session_id=session_id,
        policy=policy,
        now=clock,
        ephemeral_deleted=deleted,
    )
    return {
        "policy": policy,
        "ephemeral_deleted": deleted,
        "original_deleted": original_deleted,
        "retention_until": retention_until_for(policy, clock, event="analysis_complete").isoformat(),
    }


def persist_job_retention(
    *,
    session_id: Optional[str],
    policy: str,
    now: datetime,
    ephemeral_deleted: list[str],
) -> None:
    """Update media_assets rows. No-op without DATABASE_URL or session_id."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not session_id:
        return
    try:
        UUID(str(session_id))
    except ValueError:
        return
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        return
    until = retention_until_for(policy, now, event="analysis_complete")
    engine = create_engine(database_url)
    with engine.begin() as conn:
        if ephemeral_deleted:
            conn.execute(
                text(
                    """
                    DELETE FROM media_assets
                    WHERE session_id = CAST(:session_id AS UUID)
                      AND kind IN ('audio16k', 'analysis_proxy')
                    """
                ),
                {"session_id": session_id},
            )
        conn.execute(
            text(
                """
                UPDATE media_assets
                SET retention_until = :until
                WHERE session_id = CAST(:session_id AS UUID)
                  AND kind IN ('original', 'playback')
                """
            ),
            {"session_id": session_id, "until": until},
        )


def sweep_from_database(now: datetime, media_root: Optional[Path] = None) -> dict[str, Any]:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return {"object_count": 0, "ids": [], "kinds": {}, "now": now.isoformat()}
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, kind, storage_uri, retention_until, session_id
                FROM media_assets
                WHERE retention_until <= :now
                  AND kind IN ('original', 'playback', 'audio16k', 'analysis_proxy')
                """
            ),
            {"now": now},
        ).mappings()
        records = [
            AssetRecord(
                id=str(row["id"]),
                kind=row["kind"],
                storage_uri=row["storage_uri"],
                retention_until=row["retention_until"],
                session_id=str(row["session_id"]),
            )
            for row in rows
        ]
        result = sweep_records(records, now, media_root=media_root)
        if result["ids"]:
            for asset_id in result["ids"]:
                conn.execute(
                    text("DELETE FROM media_assets WHERE id = CAST(:id AS UUID)"),
                    {"id": asset_id},
                )
            try:
                import json
                import uuid

                conn.execute(
                    text(
                        """
                        INSERT INTO audit_log (id, action, target_type, target_id, details)
                        VALUES (
                            CAST(:id AS UUID),
                            'retention_sweeper',
                            'media_assets',
                            'expired',
                            CAST(:details AS JSONB)
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "details": json.dumps(
                            {
                                "object_count": result["object_count"],
                                "kinds": result["kinds"],
                                "id_count": len(result["ids"]),
                            }
                        ),
                    },
                )
            except Exception:
                logger.info("audit_log insert skipped (schema or connectivity)")
        return result
