"""prep_llm placeholder (issue #55). No live LLM."""

from pipeline.prep_llm import apply_prep_placeholder, placeholder_outputs


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
