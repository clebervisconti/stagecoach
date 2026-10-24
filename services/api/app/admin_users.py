"""Admin user administration. Callers must already be role=admin."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audit_events import write_audit
from app.identity_service import _now, clear_lockout, normalize_email
from app.models.user import User
from app.passwords import hash_password
from app.roles import ROLES, normalize_role


def _email(value: str) -> str:
    email = normalize_email(value)
    if "@" not in email or email.startswith("@") or email.endswith("@") or len(email) > 254:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid email address")
    return email


def _role(value: str | None, *, default: str = "member") -> str:
    try:
        return normalize_role(value, default=default)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown role") from exc


def user_view(user: User) -> dict[str, Any]:
    created = user.created_at.isoformat() if user.created_at else None
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role or "member",
        "disabled": user.disabled_at is not None,
        "must_change_password": bool(user.must_change_password),
        "online_modes": bool(user.online_modes),
        "email_verified": user.email_verified_at is not None,
        "has_password": bool(user.password_hash),
        "apple_linked": bool(user.apple_sub),
        "created_at": created,
    }


def get_active_user(db: Session, user_id: str) -> User:
    try:
        parsed = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    user = db.query(User).filter(User.id == parsed, User.deleted_at.is_(None)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def list_users(db: Session, *, q: str, limit: int, offset: int) -> tuple[list[User], int]:
    query = db.query(User).filter(User.deleted_at.is_(None))
    text = q.strip()
    if text:
        term = f"%{text}%"
        query = query.filter(or_(User.email.ilike(term), User.name.ilike(term)))
    total = query.count()
    rows = query.order_by(User.email.asc()).offset(offset).limit(limit).all()
    return rows, int(total)


def _other_active_admins(db: Session, user_id: Any) -> int:
    rows = (
        db.query(User)
        .filter(User.role == "admin", User.deleted_at.is_(None), User.disabled_at.is_(None))
        .all()
    )
    return sum(1 for row in rows if str(row.id) != str(user_id))


def _reject_self(actor: User, user: User) -> None:
    if str(actor.id) == str(user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot remove your own access")


def _reject_last_admin(db: Session, user: User) -> None:
    if (user.role or "") == "admin" and _other_active_admins(db, user.id) < 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This would remove the last admin")


def create_user(
    db: Session,
    actor: User,
    *,
    email: str,
    name: str | None,
    role: str | None,
    temp_password: str | None,
    online_modes: bool,
    ip: str | None,
) -> tuple[User, str]:
    email = _email(email)
    chosen = _role(role)
    if chosen not in ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown role")
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None and existing.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with that email already exists")
    if existing is not None and existing.deleted_at is not None:
        existing.email = f"deleted-{existing.id}@users.invalid"
        existing.apple_sub = None
    raw = temp_password if temp_password else secrets.token_urlsafe(18)
    user = User(
        email=email,
        name=(name or "").strip()[:255] or None,
        locale="en",
        timezone="UTC",
        role=chosen,
        password_hash=hash_password(raw, policy=False),
        email_verified_at=_now(),
        must_change_password=True,
        session_version=1,
        online_modes=bool(online_modes),
        failed_logins=0,
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        actor_id=actor.id,
        action="admin.user.create",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        details={"role": chosen, "online_modes": bool(online_modes)},
    )
    db.commit()
    db.refresh(user)
    return user, raw


def update_user(
    db: Session,
    actor: User,
    user: User,
    *,
    role: str | None,
    disabled: bool | None,
    online_modes: bool | None,
    name: str | None,
    ip: str | None,
) -> User:
    changed: list[str] = []
    if role is not None:
        chosen = _role(role)
        if chosen != (user.role or "member"):
            if chosen != "admin":
                _reject_self(actor, user)
                _reject_last_admin(db, user)
            elif str(actor.id) == str(user.id):
                pass
            user.role = chosen
            user.session_version = int(user.session_version or 1) + 1
            changed.append("role")
    if disabled is True and user.disabled_at is None:
        _reject_self(actor, user)
        _reject_last_admin(db, user)
        user.disabled_at = _now()
        user.session_version = int(user.session_version or 1) + 1
        changed.append("disabled")
    elif disabled is False and user.disabled_at is not None:
        user.disabled_at = None
        changed.append("enabled")
    if online_modes is not None and bool(online_modes) != bool(user.online_modes):
        user.online_modes = bool(online_modes)
        changed.append("online_modes")
    if name is not None:
        user.name = name.strip()[:255] or None
        changed.append("name")
    write_audit(
        db,
        actor_id=actor.id,
        action="admin.user.update",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        details={"fields": changed},
    )
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(
    db: Session,
    actor: User,
    user: User,
    *,
    temp_password: str | None,
    ip: str | None,
) -> str:
    raw = temp_password if temp_password else secrets.token_urlsafe(18)
    user.password_hash = hash_password(raw, policy=False)
    user.must_change_password = True
    user.session_version = int(user.session_version or 1) + 1
    clear_lockout(user)
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    write_audit(
        db,
        actor_id=actor.id,
        action="admin.user.reset",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        details={"must_change": True},
    )
    db.commit()
    return raw


def revoke_sessions(db: Session, actor: User, user: User, *, ip: str | None) -> int:
    user.session_version = int(user.session_version or 1) + 1
    write_audit(
        db,
        actor_id=actor.id,
        action="admin.user.revoke",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        details={},
    )
    db.commit()
    return int(user.session_version)


def delete_user(db: Session, actor: User, user: User, *, ip: str | None) -> None:
    _reject_self(actor, user)
    _reject_last_admin(db, user)
    user.deleted_at = _now()
    user.disabled_at = user.disabled_at or user.deleted_at
    user.email = f"deleted-{user.id}@users.invalid"
    user.apple_sub = None
    user.session_version = int(user.session_version or 1) + 1
    write_audit(
        db,
        actor_id=actor.id,
        action="admin.user.delete",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        details={},
    )
    db.commit()
