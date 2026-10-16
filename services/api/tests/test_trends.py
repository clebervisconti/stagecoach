"""Trends comparability (issue #64). No live database."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.trends_service import build_trends, major_version, session_comparable


def test_major_version_and_incompatible_reason():
    assert major_version("1.0.0") == "1"
    assert major_version("2.1.0") == "2"
    ok, reason = session_comparable(
        {"context_type": "keynote", "language": "en", "config_version": "2.0.0"},
        context="exec_briefing",
        language="en",
        config_major="1",
    )
    assert ok is False
    assert reason is not None
    assert "context" in reason
    assert "major" in reason


def test_build_trends_marks_incompatible_and_sparklines():
    rows = [
        {
            "session_id": "s-new",
            "title": "Latest",
            "created_at": "2026-10-16",
            "context_type": "exec_briefing",
            "language": "en",
            "config_version": "1.0.0",
            "overall": 72,
            "metrics": {"fl_filler_sounds_per_min": 2.8},
            "categories": {"fluency": 70},
        },
        {
            "session_id": "s-old",
            "title": "Earlier",
            "created_at": "2026-09-01",
            "context_type": "exec_briefing",
            "language": "en",
            "config_version": "1.2.0",
            "overall": 60,
            "metrics": {"fl_filler_sounds_per_min": 4.1},
            "categories": {"fluency": 55},
        },
        {
            "session_id": "s-other",
            "title": "Keynote",
            "created_at": "2026-08-01",
            "context_type": "keynote",
            "language": "en",
            "config_version": "1.0.0",
            "overall": 80,
            "metrics": {},
            "categories": {},
        },
        {
            "session_id": "s-v2",
            "title": "Re-scored",
            "created_at": "2026-07-01",
            "context_type": "exec_briefing",
            "language": "en",
            "config_version": "2.0.0",
            "overall": 90,
            "metrics": {},
            "categories": {},
        },
    ]
    body = build_trends(rows, metric="fl_filler_sounds_per_min")
    by_id = {row["session_id"]: row for row in body["series"]}
    assert by_id["s-new"]["comparable"] is True
    assert by_id["s-old"]["comparable"] is True
    assert by_id["s-other"]["comparable"] is False
    assert by_id["s-other"]["reason"] == "different context"
    assert by_id["s-v2"]["comparable"] is False
    assert "major" in (by_id["s-v2"]["reason"] or "")
    assert body["sparkline"] == [4.1, 2.8]
    assert body["most_improved"] is not None
    assert body["comparable_count"] == 2
