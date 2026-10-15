"""Talk-plan versioning and ownership (issue #55). No live database."""

import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.plans_service import (
    apply_regenerate,
    apply_user_edit,
    prep_llm_payload,
    require_owned,
)


def test_user_edit_increments_version_and_records_fields():
    plan = {"version": 1, "title": "Draft", "edit_history": []}
    now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
    updated = apply_user_edit(plan, {"title": "Board update", "slot_min": 20}, now=now)
    assert updated["version"] == 2
    assert updated["title"] == "Board update"
    assert updated["slot_min"] == 20
    assert updated["edit_history"][0]["source"] == "user"
    assert updated["edit_history"][0]["fields"] == ["slot_min", "title"]


def test_user_edit_rejects_empty_and_bad_context():
    with pytest.raises(HTTPException) as empty:
        apply_user_edit({"version": 1, "edit_history": []}, {})
    assert empty.value.status_code == 400
    with pytest.raises(HTTPException) as bad:
        apply_user_edit({"version": 1, "edit_history": []}, {"context_type": "wedding"})
    assert bad.value.status_code == 422


def test_regenerate_versions_and_strips_no_prompt():
    plan = {"version": 3, "edit_history": []}
    updated = apply_regenerate(plan, "structure", "more SCR please")
    assert updated["version"] == 4
    assert updated["status"] == "queued"
    row = updated["edit_history"][0]
    assert row["source"] == "regenerate"
    assert row["section"] == "structure"
    assert row["feedback_chars"] == len("more SCR please")
    assert "more SCR" not in str(row)


def test_regenerate_unknown_section():
    with pytest.raises(HTTPException) as exc:
        apply_regenerate({"version": 1, "edit_history": []}, "vibes", "")
    assert exc.value.status_code == 422


def test_ownership_is_404_for_other_users():
    owner = uuid4()
    other = uuid4()
    plan = SimpleNamespace(user_id=owner)
    require_owned(plan, owner)
    with pytest.raises(HTTPException) as missing:
        require_owned(None, owner)
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as hidden:
        require_owned(plan, other)
    assert hidden.value.status_code == 404


def test_prep_payload_drops_keys():
    payload = prep_llm_payload(
        "11111111-1111-4111-8111-111111111111",
        section="outline",
        feedback="shorter",
        llm_settings={"provider": "xai", "api_key": "sk-should-not-leave"},
    )
    assert payload["section"] == "outline"
    assert payload["llm_settings"] == {"provider": "xai"}
    assert "sk-should-not-leave" not in str(payload)
