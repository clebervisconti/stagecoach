"""Consent current-state, policy hash, and vision-gate helpers (issue #37)."""

import os
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.consents.policy import (
    CONSENT_PURPOSES,
    load_policy,
    localize_purpose,
    policy_version,
)
from app.consents.store import ConsentRecord, current_from_rows, snapshot_from_current


def test_policy_hash_is_sha256_and_stable():
    policy = load_policy()
    first = policy_version(policy)
    second = policy_version(load_policy())
    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)
    for purpose in CONSENT_PURPOSES:
        assert purpose in policy["purposes"]
        for locale in ("en", "pt-BR"):
            block = policy["purposes"][purpose][locale]
            for key in ("title", "what", "why", "limits", "never"):
                assert block[key]


def test_policy_text_does_not_infer_emotions():
    from pathlib import Path
    import re

    text = Path(__file__).resolve().parents[3] / "packages" / "consent" / "v1.json"
    blob = text.read_text(encoding="utf-8").lower()
    forbidden = (
        r"\bhappy\b",
        r"\bsad\b",
        r"\bangry\b",
        r"\banxious\b",
        r"\bfearful\b",
        r"\bfeliz\b",
        r"\btriste\b",
        r"\bansioso\b",
        r"\braiva\b",
        r"\bmedo\b",
        r"\bstress\b",
        r"\bengagement\b",
        r"\bauthenticity\b",
        r"\bestresse\b",
        r"\bengajamento\b",
        r"\bautenticidade\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, blob) is None, pattern
    assert "no emotion inference" in blob
    assert "não há inferência de emoção" in blob


def test_defaults_are_denied():
    snapshot = snapshot_from_current({})
    for purpose in CONSENT_PURPOSES:
        assert snapshot["purposes"][purpose]["granted"] is False
        assert snapshot["purposes"][purpose]["version"] is None


def test_latest_row_wins_and_revoke_is_recorded():
    t0 = datetime(2026, 10, 14, 12, 0, 0)
    rows = [
        ConsentRecord("video_analysis", True, "aaa", t0, None),
        ConsentRecord("video_analysis", False, "aaa", t0 + timedelta(minutes=1), t0 + timedelta(minutes=1)),
        ConsentRecord("expression_analysis", True, "aaa", t0, None),
    ]
    current = current_from_rows(rows)
    assert current["video_analysis"].granted is False
    assert current["video_analysis"].revoked_at is not None
    assert current["expression_analysis"].granted is True
    snapshot = snapshot_from_current(current)
    assert snapshot["purposes"]["video_analysis"]["granted"] is False
    assert snapshot["purposes"]["expression_analysis"]["granted"] is True
    assert snapshot["purposes"]["keep_detailed_tracking"]["granted"] is False


def test_localize_falls_back_to_english():
    block = localize_purpose("video_analysis", "fr")
    assert "pose" in block["title"].lower() or "landmarks" in block["what"].lower()
    assert "emotion" in block["never"].lower()
