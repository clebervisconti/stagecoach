"""7-day grace then hard-delete the account (SPEC §7.5 / §10.3)."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from app.deletion import (
    assert_no_content,
    audit_details,
    build_object_store,
    delete_local_prefix,
    ip_hash,
    local_session_dir,
    session_object_prefix,
)
from app.emailing import send_email
from app.models.audit_log import AuditLog
from app.models.consent import Consent
from app.models.deletion_request import DeletionRequest
from app.models.session import Session as TalkSession
from app.models.session_layout import SessionLayout
from app.models.talk_plan import Goal, TalkPlan
from app.models.user import AuthToken, User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GRACE_DAYS = 7
GRACE = timedelta(days=GRACE_DAYS)
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/data/stagecoach")).resolve()

Mailer = Callable[..., Any]


def due_at(requested_at: datetime) -> datetime:
    return requested_at + GRACE


def format_due(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_due(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=None)


def request_verification(now: datetime) -> dict[str, Any]:
    payload = {
        "status": "pending",
        "due_at": format_due(due_at(now)),
        "grace_days": GRACE_DAYS,
    }
    assert_no_content(payload)
    return payload


def is_due(verification: dict[str, Any] | None, now: datetime) -> bool:
    if not verification or verification.get("status") != "pending":
        return False
    due = parse_due(verification.get("due_at"))
    return due is not None and now >= due


def scheduled_message(*, to: str, due: datetime) -> dict[str, str]:
    when = format_due(due)
    return {
        "to": to,
        "purpose": "account_deletion_scheduled",
        "subject": "Stage Coach account deletion scheduled",
        "body": (
            "Your Stage Coach account is scheduled for deletion on "
            f"{when}. You have {GRACE_DAYS} days to cancel in Settings. "
            "After that we hard-delete your data and send a confirmation."
        ),
    }


def completed_message(*, to: str) -> dict[str, str]:
    return {
        "to": to,
        "purpose": "account_deletion",
        "subject": "Stage Coach account deleted",
        "body": (
            "Your Stage Coach account has been deleted. "
            "Sessions, scores, media, plans, and consents were removed. "
            "This is the confirmation required by the retention policy."
        ),
    }


def user_object_prefix(user_id: UUID | str) -> str:
    return f"users/{user_id}/"


def purge_user_prefixes(
    user_id: UUID | str,
    session_ids: list[UUID | str],
    store: Any,
    media_root: Path,
) -> int:
    """Remove local session dirs and object-store prefixes. Counts only."""
    deleted = 0
    for session_id in session_ids:
        try:
            directory = local_session_dir(media_root, session_id)
            deleted += delete_local_prefix(directory, media_root)
        except ValueError:
            logger.info("skip invalid local session path during account delete")
        deleted += store.delete_prefix(session_object_prefix(user_id, session_id))
    deleted += store.delete_prefix(user_object_prefix(user_id))
    return deleted


def pending_account_deletion(db: Session, user_id: UUID) -> DeletionRequest | None:
    return (
        db.query(DeletionRequest)
        .filter(
            DeletionRequest.user_id == user_id,
            DeletionRequest.scope == "account",
            DeletionRequest.completed_at.is_(None),
        )
        .order_by(DeletionRequest.requested_at.desc())
        .first()
    )


def deletion_status(row: DeletionRequest | None) -> dict[str, Any]:
    if row is None:
        return {"status": "none"}
    verification = row.verification or {}
    return {
        "status": verification.get("status") or "pending",
        "requested_at": format_due(row.requested_at) if row.requested_at else None,
        "due_at": verification.get("due_at"),
        "grace_days": verification.get("grace_days", GRACE_DAYS),
        "request_id": str(row.id),
    }


def request_account_deletion(
    db: Session,
    user: User,
    *,
    now: datetime | None = None,
    ip: str | None = None,
    mailer: Mailer | None = None,
) -> DeletionRequest:
    clock = now or datetime.utcnow()
    existing = pending_account_deletion(db, user.id)
    if existing:
        return existing
    verification = request_verification(clock)
    row = DeletionRequest(
        user_id=user.id,
        scope="account",
        requested_at=clock,
        verification=verification,
    )
    db.add(row)
    db.flush()
    db.add(
        AuditLog(
            actor_id=user.id,
            action="account.delete.request",
            target_type="account",
            target_id=str(user.id),
            at=clock,
            ip_hash=ip_hash(ip),
            details=audit_details(
                object_count=0,
                db_rows={"deletion_requests": 1},
                prefixes=[],
            ),
        )
    )
    send = mailer or send_email
    send(**scheduled_message(to=user.email, due=due_at(clock)))
    db.commit()
    db.refresh(row)
    return row


def cancel_account_deletion(
    db: Session,
    user: User,
    *,
    now: datetime | None = None,
) -> DeletionRequest | None:
    clock = now or datetime.utcnow()
    row = pending_account_deletion(db, user.id)
    if row is None:
        return None
    verification = dict(row.verification or {})
    verification["status"] = "cancelled"
    assert_no_content(verification)
    row.verification = verification
    row.completed_at = clock
    db.add(
        AuditLog(
            actor_id=user.id,
            action="account.delete.cancel",
            target_type="account",
            target_id=str(user.id),
            at=clock,
            details=audit_details(
                object_count=0,
                db_rows={"deletion_requests": 1},
                prefixes=[],
            ),
        )
    )
    db.commit()
    return row


def _account_row_counts(db: Session, user: User) -> dict[str, int]:
    session_ids = [
        row.id for row in db.query(TalkSession.id).filter(TalkSession.user_id == user.id).all()
    ]
    return {
        "sessions": len(session_ids),
        "talk_plans": db.query(TalkPlan).filter(TalkPlan.user_id == user.id).count(),
        "goals": db.query(Goal).filter(Goal.user_id == user.id).count(),
        "consents": db.query(Consent).filter(Consent.user_id == user.id).count(),
        "auth_tokens": db.query(AuthToken).filter(AuthToken.user_id == user.id).count(),
        "session_layouts": (
            db.query(SessionLayout).filter(SessionLayout.session_id.in_(session_ids)).count()
            if session_ids
            else 0
        ),
    }


def hard_delete_account(
    db: Session,
    user: User,
    row: DeletionRequest,
    *,
    now: datetime,
    store: Any,
    media_root: Path,
    mailer: Mailer | None = None,
) -> dict[str, Any]:
    """Hard-delete sessions, objects, and the user. Confirmation email. Counts only."""
    email = user.email
    user_id = user.id
    sessions = db.query(TalkSession).filter(TalkSession.user_id == user_id).all()
    session_ids = [session.id for session in sessions]
    db_rows = _account_row_counts(db, user)
    object_count = purge_user_prefixes(user_id, session_ids, store, media_root)
    for session in sessions:
        db.delete(session)
    db.flush()
    db.delete(user)
    db.flush()
    verification = {
        "status": "completed",
        "due_at": (row.verification or {}).get("due_at"),
        "grace_days": GRACE_DAYS,
        "object_count": object_count,
        "db_rows": db_rows,
        "completed_at": format_due(now),
    }
    assert_no_content(verification)
    row.completed_at = now
    row.verification = verification
    db.add(
        AuditLog(
            actor_id=None,
            action="account.delete",
            target_type="account",
            target_id=str(user_id),
            at=now,
            details=audit_details(
                object_count=object_count,
                db_rows=db_rows,
                prefixes=["local", "object_store", "account"],
            ),
        )
    )
    send = mailer or send_email
    send(**completed_message(to=email))
    logger.info(
        "account deleted sessions=%s objects=%s",
        db_rows["sessions"],
        object_count,
    )
    return {
        "user_id": str(user_id),
        "object_count": object_count,
        "db_rows": db_rows,
    }


def process_due_deletions(
    db: Session,
    *,
    now: datetime | None = None,
    store: Any | None = None,
    media_root: Path | None = None,
    mailer: Mailer | None = None,
) -> list[dict[str, Any]]:
    clock = now or datetime.utcnow()
    object_store = store if store is not None else build_object_store()
    root = media_root or MEDIA_ROOT
    rows = (
        db.query(DeletionRequest)
        .filter(
            DeletionRequest.scope == "account",
            DeletionRequest.completed_at.is_(None),
        )
        .all()
    )
    finalized: list[dict[str, Any]] = []
    for row in rows:
        if not is_due(row.verification, clock):
            continue
        if row.user_id is None:
            row.completed_at = clock
            verification = dict(row.verification or {})
            verification["status"] = "user_gone"
            row.verification = verification
            continue
        user = db.query(User).filter(User.id == row.user_id).first()
        if user is None:
            row.completed_at = clock
            verification = dict(row.verification or {})
            verification["status"] = "user_gone"
            row.verification = verification
            continue
        finalized.append(
            hard_delete_account(
                db,
                user,
                row,
                now=clock,
                store=object_store,
                media_root=root,
                mailer=mailer,
            )
        )
    db.commit()
    return finalized
