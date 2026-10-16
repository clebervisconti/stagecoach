"""prep_message_v1 + audience table (issue #57). No live LLM."""

from pipeline.prep_message import (
    MAX_CORE_WORDS,
    enforce_core_message,
    mark_unsourced_numbers,
    run_message,
    word_count,
)


def test_three_candidates_capped_at_15_words_with_claim_and_tests():
    result = run_message(
        {
            "title": "Approve the pilot workshop",
            "description": "A 20-minute exec briefing so the board will approve the pilot.",
            "context_type": "exec_briefing",
            "audience": {"roles": "executives", "decision": "approve the pilot"},
        }
    )
    assert result["prompt_id"] == "prep_message_v1"
    assert len(result["candidates"]) == 3
    for row in result["candidates"]:
        assert row["word_count"] <= MAX_CORE_WORDS
        assert word_count(row["text"]) <= MAX_CORE_WORDS
        assert row["claim_type"] in {"claim", "topic"}
        assert set(row["tests"]) >= {"so_what", "could_disagree", "simple_concrete"}
    assert result["cta"]
    assert 2 <= len(result["supporting"]) <= 4


def test_enforce_clips_long_generate_output():
    long = " ".join(["word"] * 40)
    clipped = enforce_core_message(long)
    assert word_count(clipped) == MAX_CORE_WORDS
    result = run_message(
        {"title": "Pilot", "description": "pilot", "context_type": "other"},
        generate=lambda _: {
            "candidates": [long, long, long],
            "cta": "Meet Friday",
            "supporting": ["One", "Two"],
        },
    )
    assert all(row["word_count"] <= MAX_CORE_WORDS for row in result["candidates"])


def test_unsourced_numbers_and_audience_adaptations():
    marked = mark_unsourced_numbers("Revenue grew 40 percent from 10", "we have 10 people")
    assert "40 [needs source]" in marked
    assert "10 [needs source]" not in marked
    result = run_message(
        {
            "title": "QBR",
            "description": "Use the SCR and OKR frame.",
            "context_type": "exec_briefing",
            "audience": {"roles": "C-level", "objections": "too soon"},
            "delivery_format": "in_person",
        },
        generate=lambda _: {
            "candidates": ["Approve the QBR next step now"],
            "cta": "Book the follow-up",
            "supporting": ["Revenue grew 40 last quarter", "The dated ask is Friday"],
        },
    )
    assert any("[needs source]" in item for item in result["supporting"])
    assert "Answer first" in result["audience_adaptations"]
    assert result["audience_table"]["who"] == "C-level"
    assert "SCR" in result["jargon"]
    assert "OKR" in result["jargon"]
