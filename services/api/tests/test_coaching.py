"""Objectives panel data and baseline badges. No live database."""

from types import SimpleNamespace

from app.coaching import coaching_document, remember_baseline


def test_unlinked_session_has_empty_objectives_and_no_baseline():
    body = coaching_document(
        objectives=[],
        outline=[],
        rehearsal_groups=[],
        language="en",
        history={"pp_wpm": [120.0, 130.0]},
        n_sessions=2,
        current_metrics=[{"metric_id": "pp_wpm", "raw_value": 140.0, "score": 70}],
        linked_plan=False,
    )
    assert body["objectives"] == []
    assert body["planned_vs_actual"] == []
    assert body["rehearsal_progress"]["ready"] is False
    assert body["baseline"]["ready"] is False
    assert body["badges"] == []


def test_linked_plan_shows_objectives_and_planned_minutes():
    body = coaching_document(
        objectives=[{"id": "core_message", "text": "Approve the pilot"}],
        outline=[{"section": "Opening", "minutes": 1.8}, {"section": "Close", "minutes": 2.1}],
        rehearsal_groups=[
            [{"objective_id": "cta", "status": "not_met", "score": 0.0}],
        ],
        language="en",
        history={},
        n_sessions=1,
        current_metrics=[],
        linked_plan=True,
    )
    assert body["objectives"][0]["text"] == "Approve the pilot"
    assert body["planned_vs_actual"][0]["planned_min"] == 1.8
    assert body["planned_vs_actual"][0]["actual_min"] is None
    assert body["rehearsal_progress"]["ready"] is False


def test_three_sessions_badge_keeps_population_score():
    body = coaching_document(
        objectives=[],
        outline=[],
        rehearsal_groups=[],
        language="en",
        history={"pp_wpm": [100.0, 110.0, 120.0]},
        n_sessions=3,
        current_metrics=[{"metric_id": "pp_wpm", "raw_value": 150.0, "score": 72}],
        linked_plan=False,
    )
    assert body["baseline"]["ready"] is True
    assert body["baseline"]["n_sessions"] == 3
    badge = body["badges"][0]
    assert badge["metric_id"] == "pp_wpm"
    assert badge["population_score"] == 72
    assert badge["kept_score"] == 72
    assert badge["z"] is not None


def test_remember_baseline_stores_language_snapshot():
    user = SimpleNamespace(personal_baselines=None)
    stored = remember_baseline(
        user,
        "pt-BR",
        {
            "ready": True,
            "language": "pt-BR",
            "n_sessions": 3,
            "metrics": {"pp_wpm": {"median": 120}},
        },
    )
    assert stored["pt-BR"]["n_sessions"] == 3
    assert remember_baseline(user, "en", {"ready": False}) is None
    assert "en" not in user.personal_baselines
