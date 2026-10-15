"""prep_llm placeholder persist (issue #55). Real prep_* prompts are #56–#62."""

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
        uuid.UUID(value)
        return True
    except (TypeError, ValueError):
        return False


def placeholder_outputs(section: str, feedback: str) -> dict[str, Any]:
    """Stand-in outputs so the plan is readable before LLM issues land."""
    return {
        "status": "placeholder",
        "section": section,
        "feedback_chars": len(feedback or ""),
        "note": "prep_* LLM calls land in issues #56–#62; this job only marks the plan ready.",
        "core_message": None,
        "structure": None,
        "outline": None,
        "slide_review": None,
        "time_budget": None,
        "cut_list": None,
        "rehearsal_plan": None,
        "objectives": [],
    }


def apply_prep_placeholder(
    plan_id: str,
    *,
    section: str = "all",
    feedback: str = "",
    llm_settings: Optional[dict[str, Any]] = None,
    database_url: Optional[str] = None,
) -> dict[str, Any]:
    settings = dict(llm_settings or {})
    for banned in ("api_key", "key", "secret", "token"):
        settings.pop(banned, None)
    outputs = placeholder_outputs(section, feedback)
    payload = {
        "plan_id": plan_id,
        "section": section,
        "status": "ready",
        "outputs": outputs,
        "llm_settings": settings,
    }
    url = database_url or os.getenv("DATABASE_URL")
    if not url or not _is_uuid(plan_id):
        logger.info("Skipping talk_plans persist for plan %s", plan_id)
        return payload

    engine = create_engine(url)
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE talk_plans
                SET status = 'ready',
                    outputs = CAST(:outputs AS JSONB),
                    updated_at = :now
                WHERE id = CAST(:plan_id AS UUID)
                """
            ),
            {"outputs": json.dumps(outputs), "now": now, "plan_id": plan_id},
        )
    return payload
