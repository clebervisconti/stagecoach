"""tm_section_variance and rehearsal progress (issue #63)."""

import pytest

from scoring.section_variance import (
    link_owned,
    planned_vs_actual,
    rehearsal_progress,
    tm_section_variance,
)


def test_mean_absolute_percent_deviation():
    # 10 vs 12 (+20%), 8 vs 8 (0%) → 0.10
    assert tm_section_variance([10.0, 8.0], [12.0, 8.0]) == pytest.approx(0.10)
    assert tm_section_variance([], [5.0]) is None
    assert tm_section_variance([10.0], []) == pytest.approx(1.0)


def test_planned_vs_actual_table():
    rows = planned_vs_actual(
        [{"section": "Opening", "minutes": 2.0}, {"section": "Close", "minutes": 3.0}],
        [{"section": "Opening", "minutes": 2.5}, {"section": "Close", "minutes": 2.0}],
    )
    assert [row.section for row in rows] == ["Opening", "Close"]
    assert rows[0].delta_min == pytest.approx(0.5)
    assert rows[1].delta_pct == pytest.approx(-1.0 / 3.0)


def test_rehearsal_progress_needs_two_and_tracks_status():
    short = rehearsal_progress([[{"objective_id": "cta", "status": "not_met"}]])
    assert short["ready"] is False
    body = rehearsal_progress(
        [
            [{"objective_id": "cta", "status": "not_met", "score": 0.0}],
            [{"objective_id": "cta", "status": "met", "score": 1.0}],
        ]
    )
    assert body["ready"] is True
    assert body["rehearsal_count"] == 2
    assert body["objectives"][0]["history"][0]["status"] == "not_met"
    assert body["objectives"][0]["history"][1]["status"] == "met"


def test_link_is_owner_only():
    assert link_owned(session_user_id="u1", plan_user_id="u1") is True
    assert link_owned(session_user_id="u1", plan_user_id="u2") is False
    assert link_owned(session_user_id="u1", plan_user_id=None) is False
