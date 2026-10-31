"""Copy screen_flow.json into Postgres. The file remains the source of truth."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def persist_screen_flow(
    *,
    job_id: str,
    session_id: str,
    document: dict[str, Any],
    artifact_uri: str,
    database_url: Optional[str] = None,
) -> None:
    """Upsert the view model and replace segment rows.

    No-op without DATABASE_URL or when the ids are not UUIDs. A database
    error is logged and swallowed so the analysis job still finishes.
    """
    if database_url is None:
        database_url = os.getenv("DATABASE_URL")
    if not database_url or not _is_uuid(job_id) or not _is_uuid(session_id):
        logger.info("Skipping screen flow DB persist for job %s", job_id)
        return
    try:
        _write(
            database_url=database_url,
            job_id=job_id,
            session_id=session_id,
            document=document,
            artifact_uri=artifact_uri,
        )
    except Exception:
        logger.exception("screen flow DB persist failed job=%s", job_id)


def _write(
    *,
    database_url: str,
    job_id: str,
    session_id: str,
    document: dict[str, Any],
    artifact_uri: str,
) -> None:
    engine = create_engine(database_url)
    now = datetime.utcnow()
    flow_id = str(uuid.uuid4())
    segments = list(document.get("segments") or [])
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO screen_flows (
                    id, session_id, job_id, version, delivery_mode, screen_visible_s,
                    segment_count, document, content_judgment, artifact_uri, created_at
                ) VALUES (
                    CAST(:id AS UUID), CAST(:session_id AS UUID), CAST(:job_id AS UUID),
                    :version, :delivery_mode, :screen_visible_s, :segment_count,
                    CAST(:document AS JSONB), :content_judgment, :artifact_uri, :created_at
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    version = EXCLUDED.version,
                    delivery_mode = EXCLUDED.delivery_mode,
                    screen_visible_s = EXCLUDED.screen_visible_s,
                    segment_count = EXCLUDED.segment_count,
                    document = EXCLUDED.document,
                    content_judgment = EXCLUDED.content_judgment,
                    artifact_uri = EXCLUDED.artifact_uri
                """
            ),
            {
                "id": flow_id,
                "session_id": session_id,
                "job_id": job_id,
                "version": str(document.get("version") or "1.0.0"),
                "delivery_mode": str(document.get("delivery_mode") or "webinar"),
                "screen_visible_s": float(document.get("screen_visible_s") or 0.0),
                "segment_count": len(segments),
                "document": json.dumps(document),
                "content_judgment": bool(document.get("content_judgment")),
                "artifact_uri": artifact_uri,
                "created_at": now,
            },
        )
        conn.execute(
            text("DELETE FROM screen_segments WHERE job_id = CAST(:job_id AS UUID)"),
            {"job_id": job_id},
        )
        for segment in segments:
            conn.execute(
                text(
                    """
                    INSERT INTO screen_segments (
                        id, job_id, session_id, index, t_start, t_end, dwell_s,
                        segment_type, keyframe, ocr_word_count, deck_page, activity,
                        transition_in, narration, flags, created_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:job_id AS UUID), CAST(:session_id AS UUID),
                        :index, :t_start, :t_end, :dwell_s, :segment_type, :keyframe,
                        :ocr_word_count, :deck_page, CAST(:activity AS JSONB),
                        CAST(:transition_in AS JSONB), CAST(:narration AS JSONB),
                        CAST(:flags AS JSONB), :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "session_id": session_id,
                    "index": int(segment.get("index") or 0),
                    "t_start": float(segment.get("t_start") or 0.0),
                    "t_end": float(segment.get("t_end") or 0.0),
                    "dwell_s": float(segment.get("dwell_s") or 0.0),
                    "segment_type": str(segment.get("type") or "IDLE"),
                    "keyframe": segment.get("keyframe"),
                    "ocr_word_count": int(segment.get("ocr_word_count") or 0),
                    "deck_page": segment.get("deck_page"),
                    "activity": json.dumps(segment.get("activity") or {}),
                    "transition_in": json.dumps(segment.get("transition_in")),
                    "narration": json.dumps(segment.get("narration") or {}),
                    "flags": json.dumps(segment.get("flags") or []),
                    "created_at": now,
                },
            )
