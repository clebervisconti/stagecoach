"""Retention sweeper, user policies, and ephemeral cleanup (issue #50)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pipeline.retention import (
    AFTER_ANALYSIS,
    DAYS_30,
    DEFAULT_RETENTION_DAYS,
    UNTIL_DELETE,
    UNTIL_DELETE_SENTINEL,
    AssetRecord,
    delete_ephemeral_files,
    finalize_job_media,
    retention_until_for,
    sweep_records,
)


def test_retention_until_honors_user_choices():
    now = datetime(2026, 3, 1, 12, 0, 0)
    assert retention_until_for(DAYS_30, now, "analysis_complete") == now + timedelta(
        days=DEFAULT_RETENTION_DAYS
    )
    assert retention_until_for(AFTER_ANALYSIS, now, "analysis_complete") == now
    assert retention_until_for(UNTIL_DELETE, now, "analysis_complete") == UNTIL_DELETE_SENTINEL
    assert retention_until_for(AFTER_ANALYSIS, now, "upload") == now + timedelta(days=1)
    assert retention_until_for(None, now, "upload") == now + timedelta(days=30)


def test_job_completion_deletes_audio16k_and_analysis_proxy(tmp_path: Path):
    (tmp_path / "audio16k.wav").write_bytes(b"wav")
    (tmp_path / "analysis.mp4").write_bytes(b"mp4")
    (tmp_path / "playback.mp4").write_bytes(b"keep")
    (tmp_path / "report.json").write_text("{}")
    removed = delete_ephemeral_files(tmp_path)
    assert set(removed) == {"audio16k", "analysis_proxy"}
    assert not (tmp_path / "audio16k.wav").exists()
    assert not (tmp_path / "analysis.mp4").exists()
    assert (tmp_path / "playback.mp4").exists()
    assert (tmp_path / "report.json").exists()


def test_after_analysis_deletes_original_on_finalize(tmp_path: Path):
    media = tmp_path / "media"
    session = media / "sess"
    session.mkdir(parents=True)
    original = session / "upload.bin"
    original.write_bytes(b"face-and-voice")
    job = session / "job"
    job.mkdir()
    (job / "audio16k.wav").write_bytes(b"wav")
    result = finalize_job_media(
        output_dir=job,
        input_path=original,
        retention_policy=AFTER_ANALYSIS,
        now=datetime(2026, 4, 1),
        media_root=media,
    )
    assert result["original_deleted"] is True
    assert not original.exists()
    assert "audio16k" in result["ephemeral_deleted"]


def test_until_delete_keeps_original_on_finalize(tmp_path: Path):
    original = tmp_path / "original.mp4"
    original.write_bytes(b"keep")
    (tmp_path / "audio16k.wav").write_bytes(b"wav")
    result = finalize_job_media(
        output_dir=tmp_path,
        input_path=original,
        retention_policy=UNTIL_DELETE,
        now=datetime(2026, 4, 1),
        media_root=tmp_path,
    )
    assert result["original_deleted"] is False
    assert original.exists()
    assert not (tmp_path / "audio16k.wav").exists()


def test_sweeper_time_travel_deletes_expired_originals(tmp_path: Path):
    """Integration-style clock: originals expire after the configured period."""
    now = datetime(2026, 1, 1, 0, 0, 0)
    later = now + timedelta(days=31)
    keep_until = tmp_path / "keep.mp4"
    expire = tmp_path / "expire.mp4"
    leftover = tmp_path / "audio16k.wav"
    keep_until.write_bytes(b"until-delete")
    expire.write_bytes(b"thirty-days")
    leftover.write_bytes(b"should-already-be-gone")
    records = [
        AssetRecord(
            id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            kind="original",
            storage_uri=str(keep_until),
            retention_until=UNTIL_DELETE_SENTINEL,
        ),
        AssetRecord(
            id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            kind="original",
            storage_uri=str(expire),
            retention_until=now + timedelta(days=30),
        ),
        AssetRecord(
            id="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            kind="audio16k",
            storage_uri=str(leftover),
            retention_until=now,
        ),
        AssetRecord(
            id="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            kind="deck",
            storage_uri=str(tmp_path / "deck.pptx"),
            retention_until=now,
        ),
    ]
    first = sweep_records(records, now, media_root=tmp_path)
    assert first["object_count"] == 1
    assert first["kinds"] == {"audio16k": 1}
    assert expire.exists()
    assert keep_until.exists()
    assert not leftover.exists()

    second = sweep_records(records, later, media_root=tmp_path)
    assert second["kinds"]["original"] == 1
    assert not expire.exists()
    assert keep_until.exists()
    assert "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" in second["ids"]
    assert "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" not in second["ids"]


def test_beat_schedule_registers_nightly_sweeper():
    pytest.importorskip("redis")
    pytest.importorskip("celery")
    from worker import app

    entry = app.conf.beat_schedule["retention-sweeper-nightly"]
    assert entry["task"] == "tasks.retention_sweeper"
    assert app.conf.task_routes["tasks.retention_sweeper"]["queue"] == "cpu"
