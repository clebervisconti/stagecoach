"""Persist the probed length of an original upload.

The upload handler probes with ffprobe when the API image has it. The worker
always probes during ingest validation. Either path may fill
``media_assets.duration_s``. A later write does not replace a value that is
already stored.
"""

from __future__ import annotations

import logging
import os
from uuid import UUID

logger = logging.getLogger(__name__)


def persist_original_duration(
    session_id: str,
    duration_s: float | None,
    *,
    database_url: str | None = None,
) -> bool:
    """Store duration on the original asset. False when there is nothing to do."""
    if duration_s is None:
        return False
    try:
        duration = float(duration_s)
    except (TypeError, ValueError):
        return False
    if duration <= 0 or duration != duration:
        return False
    url = os.getenv("DATABASE_URL", "") if database_url is None else database_url
    if not url or not session_id:
        return False
    try:
        UUID(str(session_id))
    except ValueError:
        return False
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(url)
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE media_assets
                    SET duration_s = :duration
                    WHERE session_id = CAST(:session_id AS UUID)
                      AND kind = 'original'
                      AND duration_s IS NULL
                    """
                ),
                {"duration": duration, "session_id": str(session_id)},
            )
            return bool(result.rowcount)
    except Exception:
        logger.exception("could not store media duration")
        return False
