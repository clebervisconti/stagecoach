"""Create the first admin from the process environment. Idempotent. Never prints the password.

Run on the server, after migrations, with the variables set in the shell only:

    BOOTSTRAP_ADMIN_EMAIL=admin@example.com \\
    BOOTSTRAP_ADMIN_TEMP_PASSWORD='(temporary)' \\
    python -m app.bootstrap_admin

Do not pass the password as an argument. Do not commit either value.
"""

from __future__ import annotations

import os
import sys

from app.audit_events import write_audit
from app.identity_service import _now, normalize_email
from app.models.user import User
from app.passwords import hash_password
from app.roles import ROLE_ADMIN


def _active_admins(db: object) -> list[User]:
    return (
        db.query(User)  # type: ignore[attr-defined]
        .filter(User.role == ROLE_ADMIN, User.deleted_at.is_(None), User.disabled_at.is_(None))
        .all()
    )


def bootstrap_admin(db: object, email: str, password: str) -> str:
    """Return created, updated, or present. Does not reset an admin who already has a password."""
    email = normalize_email(email)
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("BOOTSTRAP_ADMIN_EMAIL is not a valid email")
    if not password or not password.strip():
        raise ValueError("BOOTSTRAP_ADMIN_TEMP_PASSWORD is empty")
    existing = db.query(User).filter(User.email == email).first()  # type: ignore[attr-defined]
    admins = _active_admins(db)
    if existing is not None and existing.deleted_at is None and existing.password_hash and existing.role == ROLE_ADMIN:
        return "present"
    if existing is not None and existing.deleted_at is None and not existing.password_hash and not admins:
        existing.role = ROLE_ADMIN
        existing.password_hash = hash_password(password, policy=False)
        existing.must_change_password = True
        existing.email_verified_at = existing.email_verified_at or _now()
        existing.disabled_at = None
        existing.session_version = int(existing.session_version or 1) + 1
        existing.failed_logins = 0
        existing.locked_until = None
        write_audit(
            db,
            actor_id=existing.id,
            action="admin.bootstrap",
            target_type="user",
            target_id=str(existing.id),
            details={"result": "updated"},
        )
        db.commit()  # type: ignore[attr-defined]
        return "updated"
    if existing is not None:
        return "present"
    user = User(
        email=email,
        locale="en",
        timezone="UTC",
        role=ROLE_ADMIN,
        password_hash=hash_password(password, policy=False),
        email_verified_at=_now(),
        must_change_password=True,
        session_version=1,
        online_modes=False,
        failed_logins=0,
    )
    db.add(user)  # type: ignore[attr-defined]
    db.flush()  # type: ignore[attr-defined]
    write_audit(
        db,
        actor_id=user.id,
        action="admin.bootstrap",
        target_type="user",
        target_id=str(user.id),
        details={"result": "created"},
    )
    db.commit()  # type: ignore[attr-defined]
    return "created"


def main() -> int:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_TEMP_PASSWORD", "")
    if not email or not password:
        print(
            "bootstrap: BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_TEMP_PASSWORD are required",
            file=sys.stderr,
        )
        return 2
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        try:
            result = bootstrap_admin(db, email, password)
        except ValueError:
            print("bootstrap: failed", file=sys.stderr)
            return 1
    finally:
        db.close()
    print(f"bootstrap: {result}")
    if result in {"created", "updated"}:
        print("bootstrap: temporary password must be changed at first login")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
