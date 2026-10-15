"""Unit tests for SPEC §9.6 arithmetic and cut-list order (issue #59)."""

from datetime import date

import pytest

from scoring.time_budget import (
    CutItem,
    available_speaking_min,
    build_cut_list,
    build_time_budget,
    rehearsal_plan,
    wpm_plan,
)


def test_available_speaking_min_is_slot_minus_qa_and_buffer_times_0_9():
    assert available_speaking_min(20, qa_min=0, changeover_buffer_min=0) == pytest.approx(18.0)
    assert available_speaking_min(30, qa_min=5, changeover_buffer_min=1) == pytest.approx(21.6)


def test_available_speaking_min_rejects_non_positive():
    with pytest.raises(ValueError):
        available_speaking_min(10, qa_min=10)


def test_wpm_plan_uses_measured_median_or_130():
    assert wpm_plan(None) == 130.0
    assert wpm_plan(0) == 130.0
    assert wpm_plan(145.0) == 145.0


def test_exec_briefing_20_min_matches_spec_example():
    budget = build_time_budget(slot_min=20, body_points=3)
    assert budget.available_speaking_min == pytest.approx(18.0)
    assert budget.wpm_plan == 130.0
    assert budget.max_script_words == pytest.approx(2340.0)
    assert budget.target_script_words == pytest.approx(2106.0)
    names = [section.name for section in budget.sections]
    assert names[0] == "Opening"
    assert names[-1] == "Close"
    assert len(budget.sections) == 5  # opening + 3 body + close
    assert budget.sections[-1].cumulative_end == pytest.approx(18.0)
    opening = budget.sections[0].minutes
    close = budget.sections[-1].minutes
    body = sum(section.minutes for section in budget.sections[1:-1])
    assert opening == pytest.approx(1.8)
    assert close == pytest.approx(2.16)
    assert body == pytest.approx(14.04)


def test_cut_list_order_and_protections():
    items = [
        CutItem("hook", "hook", "cold open"),
        CutItem("story", "key_story", "Acme outage"),
        CutItem("close", "close", "CTA"),
        CutItem("must", "off_message", "legal disclaimer", must_include=True),
        CutItem("aside", "off_message", "team picnic"),
        CutItem("ex2", "extra_example", "second customer"),
        CutItem("hist", "background", "company founded in 1998"),
        CutItem("table", "detailed_data", "full cohort table"),
        CutItem("flex", "collapsible", "deep-dive appendix"),
    ]
    actions = build_cut_list(items)
    cuts = [row for row in actions if row.action == "cut"]
    assert [row.id for row in cuts] == ["aside", "ex2", "hist", "table", "flex"]
    assert [row.step for row in cuts] == [1, 2, 3, 4, 5]
    protected = {row.id for row in actions if row.action == "protect"}
    assert protected == {"hook", "story", "close", "must"}


def test_rehearsal_plan_counts_backwards_from_talk_date():
    talk = date(2026, 11, 15)
    steps = rehearsal_plan(talk, context_type="exec_briefing")
    assert steps[0].day_offset == 10
    assert steps[0].date == date(2026, 11, 5)
    assert steps[-1].day_offset == 0
    assert steps[-1].date == talk
    recorded = [row for row in steps if row.links_to_recording]
    assert len(recorded) >= 2
    keynote = rehearsal_plan(talk, context_type="keynote")
    assert any("keynote" in row.title.lower() for row in keynote)
    assert keynote[0].day_offset == 14
