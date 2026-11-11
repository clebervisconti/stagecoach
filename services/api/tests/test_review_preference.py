"""E2-7: review_layout maps onto users.layout_review_pref."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import jwt
import pytest
from fastapi import HTTPException

from app.auth import jwt as jwt_mod
from app.database import get_db
from app.main import app
from app.models.user import User
from app.passwords import hash_password
from app.rate_limit import MemoryStore
from app.routers.users import parse_review_layout
from fastapi.testclient import TestClient
from tests.memory_db import MemoryDB

SECRET = "b" * 32


def test_parse_review_layout():
    assert parse_review_layout(None) == "when_unsure"
    assert parse_review_layout("always") == "always"
    with pytest.raises(HTTPException) as exc:
        parse_review_layout("sometimes")
    assert exc.value.status_code == 422


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", SECRET)
    monkeypatch.setattr("app.rate_limit.redis.from_url", lambda *_args, **_kwargs: MemoryStore())
    db = MemoryDB()
    user = User(
        email="speaker@example.invalid",
        locale="en",
        timezone="UTC",
        password_hash=hash_password("correct-horse-battery", policy=False),
        email_verified_at=datetime.utcnow(),
        role="member",
        layout_review_pref="when_unsure",
    )
    db.add(user)
    db.flush()

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client, user
    app.dependency_overrides.clear()


def _headers(user: User) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "email": user.email,
            "sub": str(user.id),
            "sv": user.session_version or 1,
            "iss": "stagecoach-web",
            "aud": "stagecoach-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_get_and_patch_review_layout(client):
    test_client, user = client
    headers = _headers(user)
    loaded = test_client.get("/api/v1/me", headers=headers)
    assert loaded.status_code == 200
    body = loaded.json()
    assert body["review_layout"] == "when_unsure"
    assert body["confirmed_online_layouts"] == 0
    saved = test_client.patch("/api/v1/me", headers=headers, json={"review_layout": "never"})
    assert saved.status_code == 200
    assert saved.json()["review_layout"] == "never"
    assert user.layout_review_pref == "never"
    rejected = test_client.patch("/api/v1/me", headers=headers, json={"review_layout": "sometimes"})
    assert rejected.status_code == 422
    assert user.layout_review_pref == "never"
