"""Auth, RBAC, lockout, forced password change, and Apple linking without Postgres."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")
os.environ.setdefault("APPLE_CLIENT_ID", "com.stagecoach.test")
os.environ.setdefault("APPLE_TEAM_ID", "TEAMTEST1")
os.environ.setdefault("APPLE_KEY_ID", "KEYTEST1")

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from app.admin_users import delete_user
from app.apple_oidc import APPLE_ISSUER
from app.audit_events import write_audit
from app.auth import jwt as jwt_mod
from app.bootstrap_admin import bootstrap_admin, main
from app.database import get_db
from app.identity_service import (
    INVALID_LOGIN,
    _purpose_is,
    apply_apple_identity,
    reset_memory_auth_store,
)
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User
from app.passwords import hash_password
from app.rate_limit import MemoryStore
from app.roles import normalize_role
from tests.memory_db import MemoryDB

PASSWORD = "correct-horse-battery"
PASSWORD_HASH = hash_password(PASSWORD)
SECRET = "a" * 32


def _user(db: MemoryDB, email: str, **overrides: object) -> User:
    user = User(
        email=email,
        name=overrides.get("name"),
        locale="en",
        timezone="UTC",
        password_hash=overrides.get("password_hash", PASSWORD_HASH),
        email_verified_at=overrides.get("email_verified_at", datetime.utcnow()),
        role=overrides.get("role", "member"),
        must_change_password=bool(overrides.get("must_change_password", False)),
        session_version=int(overrides.get("session_version", 1)),
        online_modes=bool(overrides.get("online_modes", False)),
        failed_logins=0,
        disabled_at=overrides.get("disabled_at"),
        deleted_at=overrides.get("deleted_at"),
        apple_sub=overrides.get("apple_sub"),
    )
    db.add(user)
    db.flush()
    return user


def _bearer(user: User, *, sv: int | None = None, role_claim: str | None = None) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "email": user.email,
        "sub": str(user.id),
        "sv": user.session_version if sv is None else sv,
        "iss": "stagecoach-web",
        "aud": "stagecoach-api",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    if role_claim:
        payload["role"] = role_claim
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _details(db: MemoryDB) -> str:
    rows = db.query(AuditLog).all()
    return json.dumps([row.details for row in rows])


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", SECRET)
    monkeypatch.setattr("app.rate_limit.redis.from_url", lambda *_args, **_kwargs: MemoryStore())
    reset_memory_auth_store()
    yield
    reset_memory_auth_store()


@pytest.fixture
def ctx():
    db = MemoryDB()

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, db
    app.dependency_overrides.clear()


def test_password_policy_skips_only_for_temporary_hashes():
    hashed = hash_password("short", policy=False)
    assert hashed.startswith("$argon2id$")
    with pytest.raises(HTTPException) as exc:
        hash_password("short", policy=True)
    assert exc.value.status_code == 422


def test_purpose_compare_rejects_different_lengths():
    assert _purpose_is({"purpose": "session_ticket"}, "session_ticket") is True
    assert _purpose_is({"purpose": "session_tickeX"}, "session_ticket") is False
    assert _purpose_is({"purpose": "short"}, "session_ticket") is False


def test_normalize_role():
    assert normalize_role("Admin") == "admin"
    with pytest.raises(ValueError):
        normalize_role("owner")


def test_login_errors_do_not_enumerate(ctx, monkeypatch: pytest.MonkeyPatch):
    client, db = ctx
    member = _user(db, "member@example.com")
    _user(db, "disabled@example.com", disabled_at=datetime.utcnow())
    _user(db, "unverified@example.com", email_verified_at=None)
    calls: list[str] = []
    real = __import__("app.identity_service", fromlist=["verify_password"]).verify_password

    def spy(hashed: str, password: str) -> bool:
        calls.append(hashed)
        return real(hashed, password)

    monkeypatch.setattr("app.identity_service.verify_password", spy)
    missing = client.post("/api/v1/auth/login", json={"email": "missing@example.com", "password": "whatever-value"})
    wrong = client.post("/api/v1/auth/login", json={"email": member.email, "password": "wrong-horse-battery"})
    disabled = client.post("/api/v1/auth/login", json={"email": "disabled@example.com", "password": PASSWORD})
    unverified = client.post("/api/v1/auth/login", json={"email": "unverified@example.com", "password": PASSWORD})
    bodies = [missing.json(), wrong.json(), disabled.json(), unverified.json()]
    assert {item.status_code for item in (missing, wrong, disabled, unverified)} == {401}
    assert bodies[0] == bodies[1] == bodies[2] == bodies[3] == {"detail": INVALID_LOGIN}
    assert calls, "a missing account must still run a password verify"
    assert "@" not in _details(db)
    assert PASSWORD not in _details(db)


def test_lockout_is_the_same_401(ctx):
    client, db = ctx
    user = _user(db, "member@example.com")
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrong-horse-battery"},
        )
        assert response.status_code == 401
        assert response.json() == {"detail": INVALID_LOGIN}
    assert user.locked_until is not None
    reset_memory_auth_store()
    locked = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert locked.status_code == 401
    assert locked.json() == {"detail": INVALID_LOGIN}
    assert locked.status_code != 423


def test_login_rate_limit_is_429_without_revealing_the_account(ctx):
    client, db = ctx
    last = None
    for _ in range(5):
        last = client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.com", "password": "wrong-horse-battery"},
        )
        assert last.status_code == 401
    limited = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong-horse-battery"},
    )
    assert limited.status_code == 429
    reasons = [row.details.get("reason") for row in db.query(AuditLog).all()]
    assert "rate_limited" in reasons
    assert "@" not in _details(db)


def test_register_does_not_clobber_and_forgot_sends_no_mail(ctx, monkeypatch: pytest.MonkeyPatch):
    client, db = ctx
    user = _user(db, "member@example.com", apple_sub="apple-existing")
    sent: list[str] = []

    def record(**kwargs: object) -> None:
        sent.append(str(kwargs.get("purpose")))

    monkeypatch.setattr("app.identity_service.send_email", record)
    again = client.post(
        "/api/v1/auth/register",
        json={"email": "Member@Example.com", "password": PASSWORD},
    )
    assert again.status_code == 201
    assert again.json()["status"] == "accepted"
    assert user.password_hash == PASSWORD_HASH
    assert user.apple_sub == "apple-existing"
    assert sent == []
    forgot = client.post("/api/v1/auth/forgot", json={"email": "member@example.com"})
    assert forgot.status_code == 200
    assert forgot.json() == {"status": "accepted", "reset": "admin"}
    assert sent == []
    created = client.post(
        "/api/v1/auth/register",
        json={"email": "new-person@example.com", "password": PASSWORD},
    )
    assert created.status_code == 201
    assert sent == ["verify_email"]


def test_forced_change_blocks_the_product_until_the_password_changes(ctx):
    client, db = ctx
    admin = _user(db, "admin@example.com", role="admin")
    created = client.post(
        "/api/v1/admin/users",
        headers=_bearer(admin),
        json={"email": "member@example.com", "temp_password": "temp-pass", "role": "member"},
    )
    assert created.status_code == 201
    temp = created.json()["temporary_password"]
    assert temp == "temp-pass"
    assert temp not in _details(db)
    logged = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": temp})
    assert logged.status_code == 200
    body = logged.json()
    assert body["must_change_password"] is True
    member = db.query(User).filter(User.email == "member@example.com").first()
    assert member is not None
    old = _bearer(member)
    blocked = client.get("/api/v1/me", headers=old)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Password change required"
    changed = client.post(
        "/api/v1/auth/password",
        headers=old,
        json={"current_password": temp, "new_password": PASSWORD, "confirm_password": PASSWORD},
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert changed.json()["session_version"] == int(member.session_version)
    stale = client.get("/api/v1/me", headers=old)
    assert stale.status_code == 401
    ticket = client.post("/api/v1/auth/session-ticket", json={"ticket": body["session_ticket"]})
    assert ticket.status_code == 401
    fresh = client.get("/api/v1/me", headers=_bearer(member))
    assert fresh.status_code == 200
    assert fresh.json()["must_change_password"] is False
    assert "@" not in _details(db)
    assert temp not in _details(db)
    assert PASSWORD not in _details(db)


def test_non_admin_is_403_even_with_an_admin_claim(ctx):
    client, db = ctx
    member = _user(db, "member@example.com")
    admin = _user(db, "admin@example.com", role="admin")
    target = "11111111-1111-4111-8111-111111111199"
    checks = [
        client.get("/api/v1/admin/users", headers=_bearer(member, role_claim="admin")),
        client.post(
            "/api/v1/admin/users",
            headers=_bearer(member, role_claim="admin"),
            json={"email": "other@example.com"},
        ),
        client.patch(
            f"/api/v1/admin/users/{target}",
            headers=_bearer(member, role_claim="admin"),
            json={"role": "viewer"},
        ),
        client.delete(f"/api/v1/admin/users/{target}", headers=_bearer(member, role_claim="admin")),
        client.post(
            f"/api/v1/admin/users/{target}/reset-password",
            headers=_bearer(member, role_claim="admin"),
            json={},
        ),
        client.post(
            f"/api/v1/admin/users/{target}/revoke-sessions",
            headers=_bearer(member, role_claim="admin"),
        ),
    ]
    assert [item.status_code for item in checks] == [403, 403, 403, 403, 403, 403]
    assert {item.json()["detail"] for item in checks} == {"Admin only"}
    listed = client.get("/api/v1/admin/users", headers=_bearer(admin))
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    costs = client.get("/api/v1/admin/analysis-costs", headers=_bearer(admin))
    assert costs.status_code == 200
    denied = client.get("/api/v1/admin/analysis-costs", headers=_bearer(member))
    assert denied.status_code == 403


def test_viewer_can_read_but_not_write(ctx):
    client, db = ctx
    viewer = _user(db, "viewer@example.com", role="viewer")
    allowed = client.get("/api/v1/me", headers=_bearer(viewer))
    assert allowed.status_code == 200
    assert allowed.json()["role"] == "viewer"
    blocked = client.post(
        "/api/v1/me/consents",
        headers=_bearer(viewer),
        json={"purpose": "video_analysis", "granted": True},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Viewer accounts cannot change this resource"


def test_role_change_disable_and_revoke_invalidate_sessions(ctx):
    client, db = ctx
    admin = _user(db, "admin@example.com", role="admin")
    member = _user(db, "member@example.com")
    old = _bearer(member)
    assert client.get("/api/v1/me", headers=old).status_code == 200
    changed = client.patch(
        f"/api/v1/admin/users/{member.id}",
        headers=_bearer(admin),
        json={"role": "viewer"},
    )
    assert changed.status_code == 200
    assert client.get("/api/v1/me", headers=old).status_code == 401
    member.role = "member"
    current = _bearer(member)
    assert client.get("/api/v1/me", headers=current).status_code == 200
    disabled = client.patch(
        f"/api/v1/admin/users/{member.id}",
        headers=_bearer(admin),
        json={"disabled": True},
    )
    assert disabled.status_code == 200
    assert client.get("/api/v1/me", headers=current).status_code == 401
    client.patch(
        f"/api/v1/admin/users/{member.id}",
        headers=_bearer(admin),
        json={"disabled": False},
    )
    enabled = _bearer(member)
    assert client.get("/api/v1/me", headers=enabled).status_code == 200
    revoked = client.post(f"/api/v1/admin/users/{member.id}/revoke-sessions", headers=_bearer(admin))
    assert revoked.status_code == 200
    assert client.get("/api/v1/me", headers=enabled).status_code == 401
    assert client.get("/api/v1/me", headers=_bearer(member)).status_code == 200


def test_delete_renames_email_and_protects_the_last_admin(ctx):
    client, db = ctx
    admin = _user(db, "admin@example.com", role="admin")
    member = _user(db, "member@example.com")
    self_delete = client.delete(f"/api/v1/admin/users/{admin.id}", headers=_bearer(admin))
    assert self_delete.status_code == 409
    assert self_delete.json()["detail"] == "You cannot remove your own access"
    self_demote = client.patch(
        f"/api/v1/admin/users/{admin.id}",
        headers=_bearer(admin),
        json={"role": "member"},
    )
    assert self_demote.status_code == 409
    removed = client.delete(f"/api/v1/admin/users/{member.id}", headers=_bearer(admin))
    assert removed.status_code == 200
    assert member.email == f"deleted-{member.id}@users.invalid"
    listed = client.get("/api/v1/admin/users?q=member@example.com", headers=_bearer(admin))
    assert listed.json()["total"] == 0
    login = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": PASSWORD})
    assert login.status_code == 401
    other = _user(db, "second@example.com", role="member")
    with pytest.raises(HTTPException) as exc:
        delete_user(db, other, admin, ip=None)
    assert exc.value.status_code == 409
    assert exc.value.detail == "This would remove the last admin"


def test_admin_search_and_reset(ctx):
    client, db = ctx
    admin = _user(db, "admin@example.com", role="admin")
    _user(db, "member@example.com", name="Member Example")
    found = client.get("/api/v1/admin/users?q=member", headers=_bearer(admin))
    assert found.status_code == 200
    assert found.json()["total"] == 1
    assert found.json()["users"][0]["email"] == "member@example.com"
    reset = client.post(
        f"/api/v1/admin/users/{found.json()['users'][0]['id']}/reset-password",
        headers=_bearer(admin),
        json={"temp_password": "temp-pass"},
    )
    assert reset.status_code == 200
    assert reset.json()["must_change_password"] is True
    assert reset.json()["temporary_password"] == "temp-pass"
    assert "temp-pass" not in _details(db)


def test_bootstrap_is_idempotent_and_does_not_take_over_a_member():
    db = MemoryDB()
    assert bootstrap_admin(db, "admin@example.com", "temp-pass") == "created"
    admin = db.query(User).filter(User.email == "admin@example.com").first()
    assert admin is not None
    assert admin.role == "admin"
    assert admin.must_change_password is True
    first_hash = admin.password_hash
    assert bootstrap_admin(db, "Admin@Example.com", "different-temp") == "present"
    assert admin.password_hash == first_hash

    stub = _user(db, "stub@example.com", password_hash=None, role="member")
    assert bootstrap_admin(db, "stub@example.com", "temp-pass") == "present"
    assert stub.role == "member"
    assert stub.password_hash is None

    db.rows.remove(admin)
    assert bootstrap_admin(db, "stub@example.com", "temp-pass") == "updated"
    assert stub.role == "admin"
    assert stub.must_change_password is True
    assert stub.password_hash

    member = _user(db, "member@example.com", role="member")
    db.rows.remove(stub)
    assert bootstrap_admin(db, "member@example.com", "temp-pass") == "present"
    assert member.role == "member"
    assert member.password_hash == PASSWORD_HASH

    tombstone = _user(db, "gone@example.com", deleted_at=datetime.utcnow(), password_hash=None, role="member")
    assert bootstrap_admin(db, "gone@example.com", "temp-pass") == "present"
    assert tombstone.deleted_at is not None
    assert tombstone.role == "member"


def test_bootstrap_command_refuses_to_start_without_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_TEMP_PASSWORD", raising=False)
    assert main() == 2


def test_audit_rejects_secret_keys():
    db = MemoryDB()
    with pytest.raises(ValueError):
        write_audit(
            db,
            actor_id=None,
            action="auth.login.fail",
            target_type="user",
            target_id="unknown",
            details={"password": "nope"},
        )


def test_apple_links_only_a_verified_local_account():
    db = MemoryDB()
    verified = _user(db, "member@example.com")
    linked = apply_apple_identity(
        db,
        {"sub": "apple-1", "email": "Member@Example.com", "email_verified": True},
    )
    assert verified.apple_sub == "apple-1"
    assert linked["email"] == "member@example.com"
    again = apply_apple_identity(db, {"sub": "apple-1", "email": "member@example.com", "email_verified": "true"})
    assert again["apple_sub"] == "apple-1"

    unverified = _user(db, "unverified@example.com", email_verified_at=None)
    with pytest.raises(HTTPException) as refused:
        apply_apple_identity(
            db,
            {"sub": "apple-2", "email": "unverified@example.com", "email_verified": True},
        )
    assert refused.value.status_code == 401
    assert refused.value.detail == "Invalid Apple ID token"
    assert unverified.apple_sub is None

    taken = _user(db, "taken@example.com", apple_sub="apple-old")
    with pytest.raises(HTTPException):
        apply_apple_identity(db, {"sub": "apple-new", "email": "taken@example.com", "email_verified": True})
    assert taken.apple_sub == "apple-old"

    created = apply_apple_identity(
        db,
        {"sub": "apple-3", "email": "new-apple@example.com", "email_verified": True, "private_relay": True},
    )
    assert created["role"] == "member"
    created_row = db.query(User).filter(User.email == "new-apple@example.com").first()
    assert created_row is not None
    assert created_row.email_verified_at is not None

    disabled = _user(db, "disabled-apple@example.com", apple_sub="apple-off", disabled_at=datetime.utcnow())
    with pytest.raises(HTTPException) as blocked:
        apply_apple_identity(db, {"sub": "apple-off", "email": disabled.email, "email_verified": True})
    assert blocked.value.detail == "Invalid Apple ID token"
    assert "@" not in _details(db)


def test_apple_finish_route_still_returns_a_session_ticket(ctx, monkeypatch: pytest.MonkeyPatch):
    client, _db = ctx
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    jwk["kid"] = "test-kid"
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "iss": APPLE_ISSUER,
            "aud": "com.stagecoach.test",
            "sub": "apple-user-1",
            "email": "hidden@privaterelay.appleid.com",
            "email_verified": True,
            "nonce": "nonce-1",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )
    monkeypatch.setenv("APPLE_PRIVATE_KEY", "test-only")
    monkeypatch.setenv("APPLE_JWKS_JSON", json.dumps({"keys": [jwk]}))
    response = client.post(
        "/api/v1/auth/apple/finish",
        json={"id_token": token, "nonce": "nonce-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "hidden@privaterelay.appleid.com"
    assert body["session_ticket"]
    assert body["private_relay"] is True
    consumed = client.post("/api/v1/auth/session-ticket", json={"ticket": body["session_ticket"]})
    assert consumed.status_code == 200
    assert consumed.json()["email"] == body["email"]
    assert "session_ticket" not in consumed.json()
