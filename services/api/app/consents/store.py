"""Append-only consent current-state (SPEC §7.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from app.consents.policy import CONSENT_PURPOSES, POLICY_ID, policy_version


@dataclass(frozen=True)
class ConsentRecord:
    purpose: str
    granted: bool
    version: str
    granted_at: Optional[datetime]
    revoked_at: Optional[datetime]


def current_from_rows(rows: Iterable[ConsentRecord]) -> dict[str, ConsentRecord]:
    """Latest row per purpose. Sort is (granted_at, version) so ties are stable."""
    latest: dict[str, ConsentRecord] = {}
    ordered = sorted(
        rows,
        key=lambda row: (
            row.granted_at or datetime.min,
            row.version,
        ),
    )
    for row in ordered:
        latest[row.purpose] = row
    return latest


def empty_snapshot() -> dict:
    version = policy_version()
    return {
        "policy_id": POLICY_ID,
        "policy_version": version,
        "purposes": {
            purpose: {
                "granted": False,
                "granted_at": None,
                "revoked_at": None,
                "version": None,
            }
            for purpose in CONSENT_PURPOSES
        },
    }


def snapshot_from_current(current: dict[str, ConsentRecord]) -> dict:
    snapshot = empty_snapshot()
    for purpose, row in current.items():
        if purpose not in snapshot["purposes"]:
            continue
        snapshot["purposes"][purpose] = {
            "granted": bool(row.granted),
            "granted_at": row.granted_at.isoformat() if row.granted_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            "version": row.version,
        }
    return snapshot


def records_for_user(db, user_id) -> list[ConsentRecord]:
    from app.models.consent import Consent

    rows = db.query(Consent).filter(Consent.user_id == user_id).all()
    return [
        ConsentRecord(
            purpose=row.purpose,
            granted=bool(row.granted),
            version=row.version,
            granted_at=row.granted_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]


def snapshot_for_user(db, user_id) -> dict:
    return snapshot_from_current(current_from_rows(records_for_user(db, user_id)))
