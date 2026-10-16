"""D9 identity: argon2id, lockout, offline breach list, Apple JWKS stand-in."""

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")
os.environ["APPLE_CLIENT_ID"] = "com.stagecoach.test"
os.environ["APPLE_TEAM_ID"] = "TEAMTEST1"
os.environ["APPLE_KEY_ID"] = "KEYTEST1"

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException

from app.apple_oidc import (
    APPLE_ISSUER,
    apple_client_secret,
    apple_configured,
    authorize_url,
    is_private_relay,
    pkce_pair,
    validate_id_token,
)
from app.breached_passwords import is_breached_password
from app.emailing import clear_outbox, last_email, send_email
from app.identity_service import check_lockout, consume_auth_bucket, register_lockout_failure
from app.passwords import MIN_PASSWORD_LENGTH, hash_password, validate_password, verify_password
from app.rate_limit import MemoryStore


def _ec_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def test_argon2id_hash_and_reject_short_or_breached():
    hashed = hash_password("correct-horse-battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct-horse-battery") is True
    assert verify_password(hashed, "wrong-horse-battery") is False
    with pytest.raises(HTTPException) as short:
        validate_password("short")
    assert short.value.status_code == 422
    assert MIN_PASSWORD_LENGTH >= 10
    assert is_breached_password("password123") is True
    with pytest.raises(HTTPException) as breached:
        validate_password("password123")
    assert breached.value.status_code == 422


def test_lockout_after_five_failures():
    class FakeUser:
        failed_logins = 0
        locked_until = None

    user = FakeUser()
    for _ in range(4):
        register_lockout_failure(user)
        check_lockout(user)
    register_lockout_failure(user)
    with pytest.raises(HTTPException) as locked:
        check_lockout(user)
    assert locked.value.status_code == 423
    assert user.locked_until is not None


def test_auth_rate_limit_bucket():
    store = MemoryStore()
    now_ok = True
    for _ in range(5):
        consume_auth_bucket(store, "auth:ip:1.2.3.4")
    with pytest.raises(HTTPException) as limited:
        consume_auth_bucket(store, "auth:ip:1.2.3.4")
    assert limited.value.status_code == 429
    assert now_ok is True


def test_console_email_stand_in():
    clear_outbox()
    send_email(to="a@example.invalid", subject="Verify", body="token: abc", purpose="verify_email")
    message = last_email(purpose="verify_email")
    assert message is not None
    assert message["provider"] == "console"
    assert "abc" in message["body"]


def test_apple_disabled_without_private_key(monkeypatch):
    monkeypatch.delenv("APPLE_PRIVATE_KEY", raising=False)
    assert apple_configured() is False


def test_apple_id_token_jwks_standin_and_private_relay(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    from jwt.algorithms import RSAAlgorithm

    jwk = RSAAlgorithm.to_jwk(public, as_dict=True)
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
    claims = validate_id_token(
        token,
        nonce="nonce-1",
        audience="com.stagecoach.test",
        jwks={"keys": [jwk]},
    )
    assert claims["sub"] == "apple-user-1"
    assert claims["private_relay"] is True
    assert is_private_relay(claims["email"]) is True
    with pytest.raises(ValueError):
        validate_id_token(token, nonce="other", audience="com.stagecoach.test", jwks={"keys": [jwk]})


def test_apple_client_secret_and_authorize_url(monkeypatch):
    pem = _ec_pem()
    monkeypatch.setenv("APPLE_PRIVATE_KEY", pem)
    assert apple_configured() is True
    secret = apple_client_secret(now=1_700_000_000)
    header = jwt.get_unverified_header(secret)
    assert header["kid"] == "KEYTEST1"
    pair = pkce_pair()
    url = authorize_url(
        redirect_uri="https://app.example/auth/apple/callback",
        challenge=pair["challenge"],
        nonce=pair["nonce"],
        state=pair["state"],
    )
    assert "code_challenge_method=S256" in url
    assert "nonce=" in url
    assert pair["verifier"]
