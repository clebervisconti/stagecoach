"""prep_llm: placeholder remains for the old path; the live job writes a real plan."""

from pipeline.prep_llm import apply_prep_placeholder, apply_prep_plan, build_plan_outputs, placeholder_outputs


def test_placeholder_has_no_invented_scores():
    body = placeholder_outputs("structure", "try SCR")
    assert body["status"] == "placeholder"
    assert body["section"] == "structure"
    assert body["feedback_chars"] == len("try SCR")
    assert body["core_message"] is None
    assert body["objectives"] == []


def test_apply_skips_db_without_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = apply_prep_placeholder(
        "not-a-uuid",
        section="all",
        llm_settings={"provider": "xai", "api_key": "sk-x"},
    )
    assert result["status"] == "ready"
    assert result["llm_settings"] == {"provider": "xai"}
    assert "sk-x" not in str(result)


def test_exec_briefing_plan_has_message_and_scr():
    outputs = build_plan_outputs(
        {
            "title": "Approve the pilot",
            "description": "A 20-minute executive briefing so the board will approve the pilot.",
            "context_type": "exec_briefing",
            "slot_min": 20,
            "language": "en",
            "audience": {"roles": "executives", "decision": "approve the pilot"},
            "talk_date": "2026-11-15",
        }
    )
    assert outputs["status"] == "ready"
    assert outputs["core_message"]["source"] == "deterministic"
    assert all(row["word_count"] <= 15 for row in outputs["core_message"]["candidates"])
    assert any(row["id"] == "scr" for row in outputs["structure"]["options"])
    assert outputs["time_budget"]["available_speaking_min"] == 18
    assert [row["kind"] for row in outputs["cut_list"] if row["action"] == "cut"] == [
        "off_message",
        "extra_example",
        "background",
        "detailed_data",
        "collapsible",
    ]
    assert outputs["rehearsal_plan"]["steps"][-1]["date"] == "2026-11-15"
    assert outputs["objectives"][0]["text"]


def test_model_failure_keeps_deterministic_claim():
    def boom(_payload):
        raise ConnectionError("connection refused")

    outputs = build_plan_outputs(
        {"title": "Approve the pilot", "context_type": "exec_briefing", "slot_min": 20},
        generate=boom,
    )
    assert outputs["core_message"]["source"] == "deterministic"
    assert "unavailable" in outputs["core_message"]["model_note"]


def test_apply_prep_plan_strips_secrets_and_skips_the_model(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = apply_prep_plan(
        "not-a-uuid",
        plan={"title": "Approve the pilot", "context_type": "exec_briefing", "slot_min": 20},
        llm_settings={"provider": "local", "api_key": "sk-local"},
        use_llm=False,
    )
    assert result["llm_settings"] == {"provider": "local"}
    assert "sk-local" not in str(result)
    assert result["outputs"]["structure"]["recommended_id"] == "scr"
    assert result["outputs"]["core_message"]["source"] == "deterministic"
