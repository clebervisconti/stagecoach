"""prep_clarify_v1 (issue #56). No live LLM."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.prep_clarify import MAX_QUESTIONS, extract_fields, run_clarify


def test_extracts_slot_goal_and_decision_from_description():
    extracted = extract_fields(
        "A 20-minute exec briefing so that: the board will approve the pilot. "
        "They must decide this quarter."
    )
    assert extracted["slot_min"] == 20
    assert "approve" in extracted["goal"].lower() or extracted.get("audience_decision")
    assert extracted.get("audience_roles") == "executives"


def test_questions_cap_and_skip_writes_assumptions():
    result = run_clarify(
        {
            "description": "Tell them about the project",
            "language": "en",
            "audience": {},
        }
    )
    assert len(result["questions"]) <= MAX_QUESTIONS
    assert len(result["questions"]) >= 1
    skipped = run_clarify(
        {
            "description": "Tell them about the project",
            "language": "en",
            "audience": {},
        },
        skip=True,
    )
    assert skipped["questions"] == []
    assert skipped["skipped"] is True
    assert skipped["assumptions"]
    assert skipped["plan"]["slot_min"] == 20
    assert skipped["plan"]["goal"]
    assert skipped["plan"]["audience"]["decision"]


def test_pt_br_questions_and_cap():
    result = run_clarify(
        {
            "description": "Uma palestra",
            "language": "pt-BR",
            "audience": {},
        }
    )
    assert len(result["questions"]) <= MAX_QUESTIONS
    assert any("público" in row["prompt"].lower() or "minutos" in row["prompt"].lower() for row in result["questions"])


def test_generate_hook_merges_without_live_client():
    result = run_clarify(
        {"description": "A talk", "language": "en", "audience": {}},
        generate=lambda _: {"goal": "Ship the pilot", "slot_min": 15},
    )
    assert result["extracted"]["goal"] == "Ship the pilot"
    assert result["plan"]["slot_min"] == 15
    ids = {row["id"] for row in result["questions"]}
    assert "goal" not in ids
    assert "slot_min" not in ids
