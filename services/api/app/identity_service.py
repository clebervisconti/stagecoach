"""Password accounts, lockout, verification, Apple linking (issue #68 / D9)."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.apple_oidc import apple_configured, validate_id_token
from app.auth import jwt as jwt_mod
from app.emailing import send_email
from app.models.user import AuthToken, User, uuid7
from app.passwords import hash_password, verify_password
from app.rate_limit import MemoryStore, TokenStore, consume

LOCKOUT_FAILURES = 5
LOCKOUT_MINUTES = 15
TOKEN_TTL_HOURS = 24
MIN_PASSWORD_AUTH_RATE = 0.2  # 1 per 5s sustained
AUTH_BURST = 5


def _now() -> datetime:
    return datetime.utcnow()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_lockout(user: User) -> None:
    until = getattr(user, "locked_until", None)
    if until and until > _now():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account locked after too many failed sign-ins",
        )


def register_lockout_failure(user: User) -> None:
    user.failed_logins = int(user.failed_logins or 0) + 1
    if user.failed_logins >= LOCKOUT_FAILURES:
        user.locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
        user.failed_logins = 0


def clear_lockout(user: User) -> None:
    user.failed_logins = 0
    user.locked_until = None


def consume_auth_bucket(store: TokenStore, key: str) -> None:
    allowed, retry = consume(
        store,
        key,
        rate_per_sec=MIN_PASSWORD_AUTH_RATE,
        burst=AUTH_BURST,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts",
            headers={"Retry-After": str(max(1, int(retry + 0.999)))},
        )


def issue_token(db: Session, user: User, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    row = AuthToken(
        id=uuid7(),
        user_id=user.id,
        purpose=purpose,
        token_hash=_token_hash(raw),
        expires_at=_now() + timedelta(hours=TOKEN_TTL_HOURS),
    )
    db.add(row)
    return raw


def consume_token(db: Session, raw: str, purpose: str) -> AuthToken:
    row = (
        db.query(AuthToken)
        .filter(AuthToken.token_hash == _token_hash(raw), AuthToken.purpose == purpose)
        .first()
    )
    if row is None or row.used_at is not None or row.expires_at < _now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    row.used_at = _now()
    return row


def register_user(db: Session, email: str, password: str) -> dict[str, Any]:
    email = normalize_email(email)
    existing = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if existing and existing.password_hash:
        # Do not reveal whether the email is taken.
        return {"status": "accepted", "email": email}
    user = existing or User(email=email)
    user.password_hash = hash_password(password)
    if existing is None:
        db.add(user)
        db.flush()
    raw = issue_token(db, user, "verify_email")
    send_email(
        to=email,
        subject="Verify your Stage Coach email",
        body=f"Verification token: {raw}",
        purpose="verify_email",
    )
    db.commit()
    return {"status": "accepted", "email": email}


def verify_email(db: Session, raw: str) -> dict[str, Any]:
    row = consume_token(db, raw, "verify_email")
    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    user.email_verified_at = _now()
    db.commit()
    return {"status": "verified", "email": user.email}


def login_user(db: Session, email: str, password: str, *, store: TokenStore, ip: str) -> dict[str, Any]:
    email = normalize_email(email)
    consume_auth_bucket(store, f"auth:ip:{ip}")
    consume_auth_bucket(store, f"auth:email:{email}")
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if user is None or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    check_lockout(user)
    if user.email_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not verified")
    if not verify_password(user.password_hash, password):
        register_lockout_failure(user)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    clear_lockout(user)
    db.commit()
    return {
        "id": str(user.id),
        "email": user.email,
        "session_ticket": issue_session_ticket(str(user.id), user.email),
    }


def forgot_password(db: Session, email: str) -> dict[str, Any]:
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if user and user.password_hash:
        raw = issue_token(db, user, "reset_password")
        send_email(
            to=email,
            subject="Reset your Stage Coach password",
            body=f"Reset token: {raw}",
            purpose="reset_password",
        )
        db.commit()
    return {"status": "accepted"}


def reset_password(db: Session, raw: str, password: str) -> dict[str, Any]:
    row = consume_token(db, raw, "reset_password")
    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    user.password_hash = hash_password(password)
    clear_lockout(user)
    db.commit()
    return {"status": "reset", "email": user.email}


def apply_apple_identity(db: Session, claims: dict[str, Any]) -> dict[str, Any]:
    sub = str(claims.get("sub") or "")
    email = normalize_email(str(claims.get("email") or ""))
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Apple token missing sub")
    user = db.query(User).filter(User.apple_sub == sub, User.deleted_at.is_(None)).first()
    if user is None and email:
        user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if user is None:
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Apple did not return an email for this new account",
            )
        user = User(email=email, apple_sub=sub, email_verified_at=_now())
        db.add(user)
    else:
        user.apple_sub = sub
        if email and not user.email:
            user.email = email
        if user.email_verified_at is None:
            user.email_verified_at = _now()
    db.commit()
    db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "apple_sub": user.apple_sub,
        "private_relay": bool(claims.get("private_relay")),
        "session_ticket": issue_session_ticket(str(user.id), user.email),
    }


def finish_apple(
    db: Session,
    *,
    id_token: str,
    nonce: str,
    jwks: dict[str, Any],
) -> dict[str, Any]:
    if not apple_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sign in with Apple is not configured")
    try:
        claims = validate_id_token(id_token, nonce=nonce, jwks=jwks)
    except Exception as exc:  # noqa: BLE001 — map all JWT failures to 401
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Apple ID token") from exc
    return apply_apple_identity(db, claims)


def issue_session_ticket(user_id: str, email: str) -> str:
    if len(jwt_mod.AUTH_SECRET) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "email": email,
            "sub": user_id,
            "purpose": "session_ticket",
            "iss": jwt_mod.JWT_ISSUER,
            "aud": jwt_mod.JWT_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=2),
        },
        jwt_mod.AUTH_SECRET,
        algorithm=jwt_mod.ALGORITHM,
    )


def consume_session_ticket(ticket: str) -> dict[str, Any]:
    if len(jwt_mod.AUTH_SECRET) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")
    try:
        payload = jwt.decode(
            ticket,
            jwt_mod.AUTH_SECRET,
            algorithms=[jwt_mod.ALGORITHM],
            issuer=jwt_mod.JWT_ISSUER,
            audience=jwt_mod.JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session ticket") from exc
    if payload.get("purpose") != "session_ticket":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session ticket")
    return {"id": str(payload.get("sub")), "email": payload.get("email")}


def default_auth_store() -> TokenStore:
    if os.getenv("REDIS_URL"):
        try:
            import redis

            return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        except Exception:  # noqa: BLE001
            return MemoryStore()
    return MemoryStore()
