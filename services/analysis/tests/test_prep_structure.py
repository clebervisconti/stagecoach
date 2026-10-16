"""Structure options + outline (issue #58)."""

import pytest

from pipeline.prep_structure import ALWAYS, build_outline, run_structure, structures_for


def test_exec_briefing_offers_scr_and_at_most_two():
    options = structures_for("exec_briefing")
    assert options[0]["id"] == "scr"
    assert len(options) <= 2
    body = run_structure({"context_type": "exec_briefing", "slot_min": 20})
    assert body["prompt_id"] == "prep_structure_v1"
    assert body["recommended_id"] == "scr"
    assert len(body["options"]) <= 2


def test_opening_story_close_always_present():
    outline = build_outline({"slot_min": 20}, {"sections": ["Situation", "Complication", "Answer first"]})
    names = [row["section"] for row in outline]
    assert names[0] == ALWAYS[0][0]
    assert names[-1] == ALWAYS[2][0]
    assert any("story" in row["story_or_evidence"].lower() for row in outline)
    required = {"section", "purpose", "story_or_evidence", "transition", "target_end", "minutes"}
    for row in outline:
        assert required <= set(row)
        assert row["minutes"] > 0
    assert outline[-1]["target_end"] == pytest.approx(
        outline[-2]["target_end"] + outline[-1]["minutes"]
    )


def test_keynote_prefers_sparkline_or_hero():
    ids = {row["id"] for row in structures_for("keynote")}
    assert ids & {"sparkline", "hero"}
    assert len(structures_for("keynote")) <= 2
