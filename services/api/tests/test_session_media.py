"""Session document helpers for duration, poster, and UTC timestamps."""

import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.routers import sessions as sessions_mod

SESSION_ID = "11111111-1111-4111-8111-111111111111"
JOB_ID = "22222222-2222-4222-8222-222222222222"


def test_stored_duration_keeps_positive_probes_only():
    assert sessions_mod.stored_duration(None) is None
    assert sessions_mod.stored_duration(0) is None
    assert sessions_mod.stored_duration(-1) is None
    assert sessions_mod.stored_duration(float("nan")) is None
    assert sessions_mod.stored_duration(2149.25) == 2149.25


def test_iso_utc_marks_naive_database_timestamps_as_utc():
    naive = datetime(2026, 10, 24, 14, 58, 30)
    assert sessions_mod._iso_utc(naive) == "2026-10-24T14:58:30Z"
    aware = datetime(2026, 10, 24, 14, 58, 30, tzinfo=timezone.utc)
    assert sessions_mod._iso_utc(aware) == "2026-10-24T14:58:30Z"
    assert sessions_mod._iso_utc(None) is None


def test_poster_ready_is_the_job_poster_inside_the_media_root(tmp_path):
    root = tmp_path / "media"
    poster = root / SESSION_ID / JOB_ID / "poster.jpg"
    poster.parent.mkdir(parents=True)
    assert sessions_mod.poster_ready(root, SESSION_ID, JOB_ID) is False
    poster.write_bytes(b"jpeg")
    assert sessions_mod.poster_ready(root, SESSION_ID, JOB_ID) is True
    assert sessions_mod.poster_ready(root, SESSION_ID, None) is False
    outside = tmp_path / "poster.jpg"
    outside.write_bytes(b"nope")
    assert sessions_mod.poster_ready(root, SESSION_ID, "../..") is False
