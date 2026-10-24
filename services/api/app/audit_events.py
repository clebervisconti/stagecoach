"""Auth and admin audit rows. Payloads must not carry secrets or session content."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.deletion import assert_no_content, ip_hash
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

SECRET_MARKERS = ("password", "token", "secret", "hash", "authorization", "cookie", "ticket")


def write_audit(
    db: Any,
    *,
    actor_id: Any,
    action: str,
    target_type: str,
    target_id: str,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    payload = dict(details or {})
    for key in payload:
        lowered = key.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            raise ValueError(f"audit details must not contain {key}")
    assert_no_content(payload)
    row = AuditLog(
        actor_id=actor_id,
        action=action[:64],
        target_type=target_type[:64],
        target_id=str(target_id)[:64],
        at=datetime.utcnow(),
        ip_hash=ip_hash(ip),
        details=payload,
    )
    db.add(row)
    logger.info("audit action=%s target_type=%s", action, target_type)
    return row
