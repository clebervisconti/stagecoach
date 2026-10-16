"""7-day account deletion: grace, prefix purge, content-free audit, email."""

import logging
import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.account_deletion import (
    GRACE_DAYS,
    completed_message,
    due_at,
    format_due,
    is_due,
    purge_user_prefixes,
    request_verification,
    scheduled_message,
    user_object_prefix,
)
from app.deletion import CONTENT_KEYS, DictObjectStore, assert_no_content, session_object_prefix

USER = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SESSION_A = "11111111-1111-4111-8111-111111111111"
SESSION_B = "22222222-2222-4222-8222-222222222222"


def test_grace_period_is_seven_days():
    now = datetime(2026, 10, 16, 12, 0, 0)
    assert GRACE_DAYS == 7
    assert due_at(now) == now + timedelta(days=7)
    pending = request_verification(now)
    assert pending["status"] == "pending"
    assert pending["due_at"] == "2026-10-23T12:00:00Z"
    assert is_due(pending, now) is False
    assert is_due(pending, now + timedelta(days=6, hours=23)) is False
    assert is_due(pending, now + timedelta(days=7)) is True
    assert (
        is_due({"status": "cancelled", "due_at": pending["due_at"]}, now + timedelta(days=8))
        is False
    )
    assert_no_content(pending)


def test_confirmation_email_has_no_session_content(caplog):
    scheduled = scheduled_message(
        to="speaker@example.invalid", due=datetime(2026, 10, 23, 12, 0, 0)
    )
    done = completed_message(to="speaker@example.invalid")
    assert scheduled["purpose"] == "account_deletion_scheduled"
    assert done["purpose"] == "account_deletion"
    assert "7 days" in scheduled["body"]
    assert "deleted" in done["body"].lower()
    for message in (scheduled, done):
        lowered = message["body"].lower()
        assert "transcript" not in lowered
        assert "keynote" not in lowered
        assert "storage_uri" not in lowered
    with caplog.at_level(logging.INFO):
        logging.getLogger("app.account_deletion").info(
            "email stand-in purpose=%s provider=console", done["purpose"]
        )
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "speaker@example.invalid" not in joined
    assert done["body"] not in joined


def test_purge_user_prefixes_removes_only_that_account(tmp_path):
    root = tmp_path / "media"
    own = root / SESSION_A
    other = root / SESSION_B
    (own / "upload").mkdir(parents=True)
    (own / "upload" / "original.bin").write_bytes(b"own")
    (other / "upload").mkdir(parents=True)
    keep = other / "upload" / "keep.bin"
    keep.write_bytes(b"other")
    prefix_a = session_object_prefix(USER, SESSION_A)
    other_user = session_object_prefix("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", SESSION_B)
    store = DictObjectStore(
        [
            f"{prefix_a}original/clip.bin",
            f"{user_object_prefix(USER)}decks/slides.pptx",
            f"{other_user}original/other.bin",
        ]
    )
    deleted = purge_user_prefixes(USER, [SESSION_A], store, root)
    assert deleted == 3
    assert not own.exists()
    assert keep.is_file()
    assert store.remaining(prefix_a) == 0
    assert store.remaining(user_object_prefix(USER)) == 0
    assert store.remaining(other_user) == 1


def test_audit_payload_rejects_content_keys():
    payload = request_verification(datetime(2026, 10, 16, 8, 0, 0))
    payload["object_count"] = 2
    payload["db_rows"] = {"sessions": 1}
    assert_no_content(payload)
    with pytest.raises(ValueError):
        assert_no_content({**payload, "title": "Secret keynote"})
    for key in ("transcript", "quote", "storage_uri"):
        assert key in CONTENT_KEYS
    assert format_due(datetime(2026, 10, 16, 8, 0, 0)) == "2026-10-16T08:00:00Z"
