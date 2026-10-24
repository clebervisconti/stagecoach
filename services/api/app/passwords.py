"""argon2id hashing, minimum length, offline breached check (issue #68 / D9)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status

from app.breached_passwords import is_breached_password

# OWASP recommendation for argon2id (m=19 MiB, t=2, p=1).
HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 200
_DUMMY_HASH: str | None = None


def validate_password(password: str) -> None:
    if len(password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at most {MAX_PASSWORD_LENGTH} characters",
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    if is_breached_password(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This password appears in a common-breach list; choose another",
        )


def hash_password(password: str, *, policy: bool = True) -> str:
    """Hash a password. Temporary passwords skip the policy only when they must be changed."""
    if policy:
        validate_password(password)
    elif not password or not password.strip() or len(password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Temporary password is empty",
        )
    return HASHER.hash(password)


def dummy_password_hash() -> str:
    """Stable argon2 hash so a missing account costs the same verify as a real one."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = HASHER.hash("stagecoach-timing-stand-in")
    return _DUMMY_HASH


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return HASHER.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False
