"""AES-256-GCM for pose/face aggregates (SPEC §7.3, §10.1).

Ciphertext is written as pose.parquet / face.parquet. The file is not
plaintext Parquet; readers must decrypt first.
"""

from __future__ import annotations

import os
from typing import Optional

MAGIC = b"SCENC1"
NONCE_LEN = 12
KEY_ENV = "STAGECOACH_ARTIFACT_KEY"


class MissingArtifactKeyError(RuntimeError):
    """Raised when pose/face artifacts cannot be encrypted."""


def resolve_artifact_key(explicit: Optional[bytes] = None) -> bytes:
    if explicit is not None:
        if len(explicit) != 32:
            raise ValueError("artifact key must be 32 bytes")
        return explicit
    raw = os.environ.get(KEY_ENV, "").strip()
    if not raw:
        raise MissingArtifactKeyError(
            f"{KEY_ENV} (64 hex chars) is required to encrypt pose/face artifacts"
        )
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise MissingArtifactKeyError(f"{KEY_ENV} must be hex") from exc
    if len(key) != 32:
        raise MissingArtifactKeyError(f"{KEY_ENV} must decode to 32 bytes")
    return key


def encrypt_bytes(plaintext: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(NONCE_LEN)
    token = AESGCM(key).encrypt(nonce, plaintext, None)
    return MAGIC + nonce + token


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not blob.startswith(MAGIC):
        raise ValueError("artifact is not an encrypted Stage Coach payload")
    nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_LEN]
    token = blob[len(MAGIC) + NONCE_LEN :]
    return AESGCM(key).decrypt(nonce, token, None)


def is_encrypted(path) -> bool:
    with open(path, "rb") as handle:
        return handle.read(len(MAGIC)) == MAGIC
