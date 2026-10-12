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
