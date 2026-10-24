"""Password accounts, lockout, verification, Apple linking (ADR-057, ADR-083)."""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.apple_oidc import apple_configured, validate_id_token
from app.audit_events import write_audit
from app.auth import jwt as jwt_mod
from app.emailing import send_email
from app.models.user import AuthToken, User, uuid7
from app.passwords import dummy_password_hash, hash_password, verify_password
from app.rate_limit import MemoryStore, TokenStore, consume
from app.roles import ROLE_MEMBER

LOCKOUT_FAILURES = 5
LOCKOUT_MINUTES = 15
TOKEN_TTL_HOURS = 24
MIN_PASSWORD_AUTH_RATE = 0.2  # 1 per 5s sustained
AUTH_BURST = 5
INVALID_LOGIN = "Invalid email or password"
APPLE_LOGIN_ERROR = "Invalid Apple ID token"
_MEMORY_AUTH_STORE = MemoryStore()


def _now() -> datetime:
    return datetime.utcnow()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_digest(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()[:32]


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _invalid_login() -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_LOGIN)


def _apple_rejected() -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=APPLE_LOGIN_ERROR)


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


def _purpose_is(payload: dict[str, Any], expected: str) -> bool:
    got = str(payload.get("purpose") or "")
    if len(got) != len(expected):
        return False
    return secrets.compare_digest(got, expected)


def _apple_email_verified(claims: dict[str, Any]) -> bool:
    value = claims.get("email_verified")
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() == "true":
        return True
    return False


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


def _active_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()


def register_user(db: Session, email: str, password: str) -> dict[str, Any]:
    email = normalize_email(email)
    # Hash before the lookup so an existing account is not cheaper to probe.
    hashed = hash_password(password)
    existing = _active_user_by_email(db, email)
    if existing is not None:
        # Do not attach a password to an Apple-only or existing account, and do not say which.
        return {"status": "accepted", "email": email}
    user = User(
        email=email,
        locale="en",
        timezone="UTC",
        password_hash=hashed,
        role=ROLE_MEMBER,
        session_version=1,
        must_change_password=False,
        online_modes=False,
        failed_logins=0,
    )
    db.add(user)
    db.flush()
    raw = issue_token(db, user, "verify_email")
    send_email(to=email, purpose="verify_email", token=raw)
    write_audit(
        db,
        actor_id=user.id,
        action="auth.register",
        target_type="user",
        target_id=str(user.id),
        details={"role": ROLE_MEMBER},
    )
    db.commit()
    return {"status": "accepted", "email": email}


def verify_email(db: Session, raw: str) -> dict[str, Any]:
    row = consume_token(db, raw, "verify_email")
    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    user.email_verified_at = _now()
    write_audit(
        db,
        actor_id=user.id,
        action="auth.email.verify",
        target_type="user",
        target_id=str(user.id),
        details={},
    )
    db.commit()
    return {"status": "verified", "email": user.email}


def _fail_login(db: Session, *, user: User | None, email: str, reason: str, ip: str) -> None:
    write_audit(
        db,
        actor_id=user.id if user is not None else None,
        action="auth.login.fail",
        target_type="user",
        target_id=str(user.id) if user is not None else "unknown",
        ip=ip,
        details={"reason": reason, "email_digest": email_digest(email)},
    )
    db.commit()
    _invalid_login()


def login_user(db: Session, email: str, password: str, *, store: TokenStore, ip: str) -> dict[str, Any]:
    email = normalize_email(email)
    try:
        consume_auth_bucket(store, f"auth:ip:{ip}")
        consume_auth_bucket(store, f"auth:email:{email_digest(email)}")
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            write_audit(
                db,
                actor_id=None,
                action="auth.login.fail",
                target_type="user",
                target_id="unknown",
                ip=ip,
                details={"reason": "rate_limited"},
            )
            db.commit()
        raise
    user = _active_user_by_email(db, email)
    if user is None or not user.password_hash:
        verify_password(dummy_password_hash(), password)
        _fail_login(db, user=user, email=email, reason="invalid", ip=ip)
    assert user is not None and user.password_hash
    password_ok = verify_password(user.password_hash, password)
    locked = bool(user.locked_until and user.locked_until > _now())
    if locked:
        _fail_login(db, user=user, email=email, reason="locked", ip=ip)
    if user.disabled_at is not None:
        _fail_login(db, user=user, email=email, reason="disabled", ip=ip)
    if not password_ok:
        register_lockout_failure(user)
        reason = "locked" if user.locked_until and user.locked_until > _now() else "invalid"
        _fail_login(db, user=user, email=email, reason=reason, ip=ip)
    if user.email_verified_at is None:
        _fail_login(db, user=user, email=email, reason="unverified", ip=ip)
    clear_lockout(user)
    write_audit(
        db,
        actor_id=user.id,
        action="auth.login.ok",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        details={"method": "password"},
    )
    db.commit()
    db.refresh(user)
    return public_identity(user)


def forgot_password(db: Session, email: str) -> dict[str, Any]:
    """Admin reset only. Do not look up the account or send mail (ADR-083)."""
    normalize_email(email)
    _ = db
    return {"status": "accepted", "reset": "admin"}


def reset_password(db: Session, raw: str, password: str) -> dict[str, Any]:
    """Consume a previously issued reset token. New tokens are not emailed."""
    row = consume_token(db, raw, "reset_password")
    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.session_version = int(user.session_version or 1) + 1
    clear_lockout(user)
    write_audit(
        db,
        actor_id=user.id,
        action="auth.password.change",
        target_type="user",
        target_id=str(user.id),
        details={"via": "token"},
    )
    db.commit()
    return {"status": "reset", "email": user.email}


def change_password(
    db: Session,
    user: User,
    *,
    current_password: str | None,
    new_password: str,
    confirm_password: str,
    ip: str,
) -> dict[str, Any]:
    if new_password != confirm_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Passwords do not match")
    if user.password_hash:
        if not current_password or not verify_password(user.password_hash, current_password):
            write_audit(
                db,
                actor_id=user.id,
                action="auth.password.fail",
                target_type="user",
                target_id=str(user.id),
                ip=ip,
                details={"reason": "current"},
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
        if current_password == new_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Choose a different password",
            )
    hashed = hash_password(new_password)
    user.password_hash = hashed
    user.must_change_password = False
    user.session_version = int(user.session_version or 1) + 1
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    clear_lockout(user)
    write_audit(
        db,
        actor_id=user.id,
        action="auth.password.change",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        details={"via": "session"},
    )
    db.commit()
    db.refresh(user)
    return public_identity(user)


def _safe_to_link(candidate: User) -> bool:
    """Link Apple to an existing row only when that cannot steal an unverified password account."""
    if candidate.apple_sub:
        return False
    if candidate.disabled_at is not None or candidate.deleted_at is not None:
        return False
    if candidate.password_hash and candidate.email_verified_at is None:
        return False
    return True


def apply_apple_identity(db: Session, claims: dict[str, Any]) -> dict[str, Any]:
    sub = str(claims.get("sub") or "")
    email = normalize_email(str(claims.get("email") or ""))
    if not sub:
        _apple_rejected()
    verified = _apple_email_verified(claims)
    user = db.query(User).filter(User.apple_sub == sub, User.deleted_at.is_(None)).first()
    linked = False
    created = False
    if user is None and email and verified:
        candidate = _active_user_by_email(db, email)
        if candidate is not None:
            if candidate.apple_sub and candidate.apple_sub != sub:
                write_audit(
                    db,
                    actor_id=candidate.id,
                    action="auth.apple.refuse",
                    target_type="user",
                    target_id=str(candidate.id),
                    details={"reason": "different_apple_sub"},
                )
                db.commit()
                _apple_rejected()
            if not _safe_to_link(candidate):
                write_audit(
                    db,
                    actor_id=candidate.id,
                    action="auth.apple.refuse",
                    target_type="user",
                    target_id=str(candidate.id),
                    details={"reason": "unverified_local"},
                )
                db.commit()
                _apple_rejected()
            candidate.apple_sub = sub
            if candidate.email_verified_at is None:
                candidate.email_verified_at = _now()
            user = candidate
            linked = True
        else:
            user = User(
                email=email,
                locale="en",
                timezone="UTC",
                apple_sub=sub,
                email_verified_at=_now(),
                role=ROLE_MEMBER,
                session_version=1,
                must_change_password=False,
                online_modes=False,
                failed_logins=0,
            )
            db.add(user)
            db.flush()
            created = True
    elif user is None:
        write_audit(
            db,
            actor_id=None,
            action="auth.apple.refuse",
            target_type="user",
            target_id="unknown",
            details={"reason": "unverified_email"},
        )
        db.commit()
        _apple_rejected()
    assert user is not None
    if user.disabled_at is not None or user.deleted_at is not None:
        write_audit(
            db,
            actor_id=user.id,
            action="auth.apple.refuse",
            target_type="user",
            target_id=str(user.id),
            details={"reason": "disabled"},
        )
        db.commit()
        _apple_rejected()
    action = "auth.apple.create" if created else "auth.apple.link" if linked else "auth.apple.ok"
    write_audit(
        db,
        actor_id=user.id,
        action=action,
        target_type="user",
        target_id=str(user.id),
        details={"private_relay": bool(claims.get("private_relay"))},
    )
    db.commit()
    db.refresh(user)
    body = public_identity(user)
    body["apple_sub"] = user.apple_sub
    body["private_relay"] = bool(claims.get("private_relay"))
    return body


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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=APPLE_LOGIN_ERROR) from exc
    return apply_apple_identity(db, claims)


def public_identity(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role or ROLE_MEMBER,
        "must_change_password": bool(user.must_change_password),
        "session_version": int(user.session_version or 1),
        "session_ticket": issue_session_ticket(user),
    }


def issue_session_ticket(user: User) -> str:
    if len(jwt_mod.AUTH_SECRET) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "email": user.email,
            "sub": str(user.id),
            "purpose": "session_ticket",
            "role": user.role or ROLE_MEMBER,
            "sv": int(user.session_version or 1),
            "must_change_password": bool(user.must_change_password),
            "iss": jwt_mod.JWT_ISSUER,
            "aud": jwt_mod.JWT_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=2),
        },
        jwt_mod.AUTH_SECRET,
        algorithm=jwt_mod.ALGORITHM,
    )


def consume_session_ticket(db: Session, ticket: str) -> dict[str, Any]:
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
    if not _purpose_is(payload, "session_ticket"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session ticket")
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session ticket") from exc
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    claimed = payload.get("sv")
    try:
        claimed_sv = int(claimed)
    except (TypeError, ValueError):
        claimed_sv = -1
    if user is None or user.disabled_at is not None or claimed_sv != int(user.session_version or 1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session ticket")
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role or ROLE_MEMBER,
        "must_change_password": bool(user.must_change_password),
        "session_version": int(user.session_version or 1),
    }


def default_auth_store() -> TokenStore:
    if os.getenv("REDIS_URL"):
        try:
            import redis

            return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        except Exception:  # noqa: BLE001
            return _MEMORY_AUTH_STORE
    return _MEMORY_AUTH_STORE


def reset_memory_auth_store() -> None:
    _MEMORY_AUTH_STORE.clear()
