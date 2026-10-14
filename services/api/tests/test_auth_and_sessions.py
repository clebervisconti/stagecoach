"""API auth and session-path containment tests (no live database)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
import jwt

# Importing the FastAPI dependency graph constructs an engine but does not
# connect. Unit tests still supply an explicit non-secret URL to fail closed.
os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.auth import jwt as jwt_mod
from app.routers import sessions as sessions_mod


def test_verify_token_requires_issuer_audience_and_expiry(monkeypatch):
    secret = "a" * 32
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", secret)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "email": "beta@example.invalid",
            "sub": "beta@example.invalid",
            "iss": "stagecoach-web",
            "aud": "stagecoach-api",
            "iat": now,
            "nbf": now - timedelta(seconds=5),
            "exp": now + timedelta(minutes=1),
        },
        secret,
        algorithm="HS256",
    )

    class Creds:
        credentials = token

    payload = jwt_mod.verify_token(Creds())
    assert payload["email"] == "beta@example.invalid"


def test_verify_token_rejects_token_without_expiry(monkeypatch):
    secret = "a" * 32
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", secret)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "email": "beta@example.invalid",
            "sub": "beta@example.invalid",
            "iss": "stagecoach-web",
            "aud": "stagecoach-api",
            "iat": now,
        },
        secret,
        algorithm="HS256",
    )

    class Creds:
        credentials = token

    with pytest.raises(HTTPException) as exc:
        jwt_mod.verify_token(Creds())
    assert exc.value.status_code == 401


def test_verify_token_rejects_wrong_audience(monkeypatch):
    secret = "a" * 32
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", secret)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "email": "beta@example.invalid",
            "sub": "beta@example.invalid",
            "iss": "stagecoach-web",
            "aud": "someone-else",
            "iat": now,
            "exp": now + timedelta(minutes=1),
        },
        secret,
        algorithm="HS256",
    )

    class Creds:
        credentials = token

    with pytest.raises(HTTPException) as exc:
        jwt_mod.verify_token(Creds())
    assert exc.value.status_code == 401


def test_safe_artifact_path_rejects_escape(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    media_root.mkdir()
    inside = media_root / "session" / "report.json"
    inside.parent.mkdir()
    inside.write_text("{}")
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    monkeypatch.setattr(sessions_mod, "MEDIA_ROOT", media_root.resolve())
    resolved = sessions_mod._safe_artifact_path(str(inside))
    assert resolved == inside.resolve()
    with pytest.raises(HTTPException) as escaped:
        sessions_mod._safe_artifact_path(str(outside))
    assert escaped.value.status_code == 404


def test_playback_signature_roundtrip_and_reject_tamper(monkeypatch):
    secret = "b" * 32
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", secret)
    exp = 1_800_000_000
    sig = sessions_mod.sign_playback("sess-1", exp)
    assert sessions_mod.verify_playback("sess-1", exp, sig) is True
    assert sessions_mod.verify_playback("sess-2", exp, sig) is False
    assert sessions_mod.verify_playback("sess-1", exp + 1, sig) is False
    assert sessions_mod.PLAYBACK_TTL_S == 15 * 60


def test_highlights_come_only_from_existing_evidence():
    report = {
        "evidence": [
            {
                "kind": "observation",
                "category_id": "fluency",
                "metric_id": "fl_filler_sounds_per_min",
                "t_start": 0.0,
                "t_end": 1.2,
                "text": "Measured filler-sound rate 2.00 per minute.",
                "quote": None,
                "user_disputed": False,
            }
        ]
    }
    highlights = sessions_mod._highlights_from_artifacts({"segments": []}, report)
    assert len(highlights) == 1
    assert highlights[0]["metric_id"] == "fl_filler_sounds_per_min"
    assert sessions_mod._highlights_from_artifacts({"segments": []}, None) == []


def test_video_series_placeholder_is_one_second():
    series = sessions_mod._empty_series("gesture", 3.2)
    assert series["resolution_s"] == 1
    assert series["unavailable"] is True
    assert len(series["points"]) == 3
    assert all(p["value"] is None for p in series["points"])


def test_token_bucket_denies_after_burst():
    from app.rate_limit import MemoryStore, consume

    store = MemoryStore()
    now = 1_000_000.0
    allowed = 0
    denied = 0
    for _ in range(5):
        ok, _retry = consume(store, "rl:test", rate_per_sec=1, burst=3, now=now)
        if ok:
            allowed += 1
        else:
            denied += 1
    assert allowed == 3
    assert denied == 2
    ok, _retry = consume(store, "rl:test", rate_per_sec=1, burst=3, now=now + 2)
    assert ok is True
