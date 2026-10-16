"""Goals create/progress (issue #65). No live database."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import pytest
from fastapi import HTTPException

from app.goals_service import apply_progress, goal_met, progress_label, validate_goal


def test_validate_requires_one_target_and_known_comparator():
    validate_goal("fl_filler_sounds_per_min", None, "<")
    with pytest.raises(HTTPException) as both:
        validate_goal("fl_filler_sounds_per_min", "fluency", "<")
    assert both.value.status_code == 422
    with pytest.raises(HTTPException) as bad:
        validate_goal("fl_filler_sounds_per_min", None, "≈")
    assert bad.value.status_code == 422


def test_progress_sets_achieved_at_once():
    assert goal_met(2.8, "<", 3.0) is True
    assert goal_met(3.6, "<", 3.0) is False
    first = apply_progress(
        {"metric_id": "fl_filler_sounds_per_min", "comparator": "<", "target": 3.0},
        2.8,
    )
    assert first["achieved_at"]
    assert "✓" in progress_label(first)
    locked = apply_progress({**first, "achieved_at": "2026-01-01T00:00:00+00:00"}, 4.0)
    assert locked["achieved_at"] == "2026-01-01T00:00:00+00:00"
