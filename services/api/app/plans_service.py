"""Talk-plan versioning, ownership, and prep_llm enqueue payload (issue #55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status

CONTEXT_TYPES = (
    "keynote",
    "breakout",
    "exec_briefing",
    "sales_pitch",
    "virtual_meeting",
    "class_academic",
    "other",
)
LANGUAGES = ("en", "pt-BR")
REGENERATE_SECTIONS = frozenset(
    {
        "all",
        "core_message",
        "audience",
        "structure",
        "outline",
        "slide_review",
        "time_budget",
        "cut_list",
        "rehearsal_plan",
        "objectives",
    }
)
USER_EDIT_FIELDS = (
    "title",
    "context_type",
    "description",
    "audience",
    "goal",
    "slot_min",
    "qa_in_slot",
    "qa_min",
    "language",
    "constraints",
    "script_text",
    "outputs",
    "talk_date",
    "delivery_format",
    "known_habits",
    "must_include",
)


def require_owned(plan: Any, user_id: Any) -> None:
    """404 when missing or not owned — do not leak another user's plan id."""
    if plan is None or str(getattr(plan, "user_id", "")) != str(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")


def apply_user_edit(
    plan: dict[str, Any],
    patch: dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Increment version and append a history row for user field edits."""
    changed = {key: patch[key] for key in USER_EDIT_FIELDS if key in patch}
    if not changed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No editable fields")
    if "context_type" in changed and changed["context_type"] not in CONTEXT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid context_type")
    if "language" in changed and changed["language"] not in LANGUAGES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid language")

    stamp = now or datetime.now(timezone.utc)
    history = list(plan.get("edit_history") or [])
    next_version = int(plan.get("version") or 1) + 1
    history.append(
        {
            "version": next_version,
            "at": stamp.replace(microsecond=0).isoformat(),
            "source": "user",
            "fields": sorted(changed.keys()),
        }
    )
    updated = dict(plan)
    updated.update(changed)
    updated["version"] = next_version
    updated["edit_history"] = history
    return updated


def apply_regenerate(
    plan: dict[str, Any],
    section: str,
    feedback: str,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    if section not in REGENERATE_SECTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown section {section}",
        )
    stamp = now or datetime.now(timezone.utc)
    history = list(plan.get("edit_history") or [])
    next_version = int(plan.get("version") or 1) + 1
    history.append(
        {
            "version": next_version,
            "at": stamp.replace(microsecond=0).isoformat(),
            "source": "regenerate",
            "section": section,
            "feedback_chars": len(feedback or ""),
        }
    )
    updated = dict(plan)
    updated["version"] = next_version
    updated["edit_history"] = history
    updated["status"] = "queued"
    return updated


def prep_llm_payload(
    plan_id: str,
    *,
    section: str = "all",
    feedback: str = "",
    llm_settings: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    settings = dict(llm_settings or {})
    for banned in ("api_key", "key", "secret", "token"):
        settings.pop(banned, None)
    return {
        "plan_id": plan_id,
        "section": section,
        "feedback": feedback,
        "llm_settings": settings,
    }
