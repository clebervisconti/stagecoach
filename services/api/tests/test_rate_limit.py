"""Per-user rate-limit keys. The JWT header is not a user id."""

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import jwt as jwt_mod
from app.rate_limit import MemoryStore, TokenBucketMiddleware, user_rate_key

SESSION_ID = "11111111-1111-4111-8111-111111111111"


def _token(secret: str, sub: str) -> str:
    now = datetime.now(timezone.utc)
    encoded = jwt.encode(
        {
            "sub": sub,
            "email": f"{sub}@example.invalid",
            "iss": "stagecoach-web",
            "aud": "stagecoach-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )
    return encoded if isinstance(encoded, str) else encoded.decode()


def _app(monkeypatch, store: MemoryStore, *, user_burst: float = 2, ip_burst: float = 80):
    secret = "c" * 32
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", secret)
    monkeypatch.setattr("app.rate_limit.USER_BURST", user_burst)
    monkeypatch.setattr("app.rate_limit.USER_RATE_PER_SEC", 0.0)
    monkeypatch.setattr("app.rate_limit.IP_BURST", ip_burst)
    monkeypatch.setattr("app.rate_limit.IP_RATE_PER_SEC", 0.0)
    app = FastAPI()
    app.add_middleware(TokenBucketMiddleware, store=store)

    @app.get("/api/v1/me")
    def me():
        return {"ok": True}

    @app.get("/api/v1/ping")
    def ping():
        return {"ok": True}

    @app.get("/api/v1/sessions/{session_id}")
    def session_document(session_id: str):
        return {"id": session_id}

    @app.get("/api/v1/sessions/{session_id}/events")
    def events(session_id: str):
        return {"id": session_id}

    @app.get("/api/v1/sessions/{session_id}/report")
    def report(session_id: str):
        return {"id": session_id}

    return TestClient(app), secret


def test_two_users_do_not_share_a_bucket_when_the_jwt_prefix_matches(monkeypatch):
    store = MemoryStore()
    client, secret = _app(monkeypatch, store)
    token_a = _token(secret, "user-a")
    token_b = _token(secret, "user-b")
    assert token_a[:32] == token_b[:32]
    assert token_a != token_b
    assert user_rate_key(f"Bearer {token_a}") == "rl:user:user-a"
    assert user_rate_key(f"Bearer {token_b}") == "rl:user:user-b"
    assert f"rl:user:{token_a[:32]}" not in {user_rate_key(f"Bearer {token_a}"), user_rate_key(f"Bearer {token_b}")}

    for _ in range(2):
        allowed = client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_a}"})
        assert allowed.status_code == 200
    denied = client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_a}"})
    assert denied.status_code == 429
    assert denied.headers["retry-after"].isdigit()
    assert int(denied.headers["retry-after"]) >= 1
    other = client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_b}"})
    assert other.status_code == 200
    assert "rl:user:user-a" in store._data
    assert "rl:user:user-b" in store._data


def test_token_prefix_collision_does_not_share_a_bucket(monkeypatch):
    store = MemoryStore()
    client, _secret = _app(monkeypatch, store)
    prefix = "x" * 32
    token_a = prefix + ".body-a"
    token_b = prefix + ".body-b"
    assert token_a[:32] == token_b[:32]
    key_a = user_rate_key(f"Bearer {token_a}")
    key_b = user_rate_key(f"Bearer {token_b}")
    assert key_a != key_b
    assert key_a.startswith("rl:user:token:")
    assert key_b.startswith("rl:user:token:")

    for _ in range(2):
        assert client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_a}"}).status_code == 200
    denied = client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_a}"})
    assert denied.status_code == 429
    assert int(denied.headers["retry-after"]) >= 1
    assert client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_b}"}).status_code == 200


def test_session_reads_skip_the_user_bucket_and_keep_the_ip_bucket(monkeypatch):
    store = MemoryStore()
    client, secret = _app(monkeypatch, store, user_burst=1, ip_burst=40)
    token = _token(secret, "user-a")
    headers = {"Authorization": f"Bearer {token}"}
    document = f"/api/v1/sessions/{SESSION_ID}"
    for _ in range(3):
        assert client.get("/api/v1/me", headers=headers).status_code == 200
        assert client.get(document, headers=headers).status_code == 200
        assert client.get(f"{document}/events", headers=headers).status_code == 200
    assert not any(key.startswith("rl:user:") for key in store._data)
    assert any(key.startswith("rl:ip:") for key in store._data)

    assert client.get(f"{document}/report", headers=headers).status_code == 200
    assert "rl:user:user-a" in store._data
    limited = client.get(f"{document}/report", headers=headers)
    assert limited.status_code == 429
    assert client.get(document, headers=headers).status_code == 200


def test_unauthenticated_requests_are_limited_by_ip_only(monkeypatch):
    store = MemoryStore()
    client, _secret = _app(monkeypatch, store, ip_burst=2)
    assert client.get("/api/v1/ping").status_code == 200
    assert client.get("/api/v1/ping").status_code == 200
    denied = client.get("/api/v1/ping")
    assert denied.status_code == 429
    assert denied.headers["retry-after"].isdigit()
    assert not any(key.startswith("rl:user:") for key in store._data)
    assert any(key.startswith("rl:ip:") for key in store._data)
    assert user_rate_key(None) is None
    assert user_rate_key("Bearer ") is None
