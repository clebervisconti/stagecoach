"""AES-256-GCM for pose/face aggregates and biometric JSON (SPEC §7.3, §10.1, §10.5).

SCENC1: single-key AES-GCM (pose.parquet / face.parquet).
SCENC2: envelope — a random DEK encrypts the payload; the DEK is wrapped with a
local KEK (`STAGECOACH_KEK` or `STAGECOACH_ARTIFACT_KEY`). A KMS KEK provider
is an owner decision and is not selected here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol

MAGIC = b"SCENC1"
MAGIC_V2 = b"SCENC2"
NONCE_LEN = 12
DEK_LEN = 32
GCM_TAG_LEN = 16
WRAPPED_DEK_LEN = DEK_LEN + GCM_TAG_LEN
KEY_ENV = "STAGECOACH_ARTIFACT_KEY"
KEK_ENV = "STAGECOACH_KEK"
KMS_PROVIDER_ENV = "STAGECOACH_KMS_PROVIDER"


class MissingArtifactKeyError(RuntimeError):
    """Raised when pose/face artifacts cannot be encrypted."""


class KekProvider(Protocol):
    """Wraps/unwraps data-encryption keys. Local KEK in dev; KMS later."""

    kek_id: str

    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes]: ...

    def unwrap(self, nonce: bytes, wrapped: bytes, aad: bytes) -> bytes: ...


class LocalKekProvider:
    """AES-GCM wrap with a 32-byte local KEK (dev / private beta)."""

    def __init__(self, key: bytes, kek_id: str = "local") -> None:
        if len(key) != 32:
            raise ValueError("KEK must be 32 bytes")
        self._key = key
        self.kek_id = kek_id

    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(NONCE_LEN)
        return nonce, AESGCM(self._key).encrypt(nonce, dek, aad)

    def unwrap(self, nonce: bytes, wrapped: bytes, aad: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        return AESGCM(self._key).decrypt(nonce, wrapped, aad)


class OwnerKmsKekProvider:
    """Placeholder. KMS vendor / key policy is an owner decision (SPEC §1.2)."""

    kek_id = "kms"

    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes]:
        raise RuntimeError("KMS envelope wrapping is not configured; owner decision pending")

    def unwrap(self, nonce: bytes, wrapped: bytes, aad: bytes) -> bytes:
        raise RuntimeError("KMS envelope unwrapping is not configured; owner decision pending")


def _parse_hex_key(raw: str, env_name: str) -> bytes:
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise MissingArtifactKeyError(f"{env_name} must be hex") from exc
    if len(key) != 32:
        raise MissingArtifactKeyError(f"{env_name} must decode to 32 bytes")
    return key


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
    return _parse_hex_key(raw, KEY_ENV)


def resolve_kek(explicit: Optional[bytes] = None) -> bytes:
    """Local KEK: STAGECOACH_KEK, else the artifact key (dev convenience)."""
    if explicit is not None:
        return resolve_artifact_key(explicit)
    raw = os.environ.get(KEK_ENV, "").strip()
    if raw:
        return _parse_hex_key(raw, KEK_ENV)
    return resolve_artifact_key()


def resolve_kek_provider(explicit: Optional[bytes] = None) -> KekProvider:
    if os.environ.get(KMS_PROVIDER_ENV, "").strip():
        return OwnerKmsKekProvider()
    return LocalKekProvider(resolve_kek(explicit), kek_id="local")


def encrypt_bytes(plaintext: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(NONCE_LEN)
    token = AESGCM(key).encrypt(nonce, plaintext, None)
    return MAGIC + nonce + token


def encrypt_envelope(
    plaintext: bytes,
    kek: bytes,
    kek_id: str = "local",
) -> bytes:
    """SCENC2: DEK-encrypt payload, wrap the DEK with the KEK."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    provider = LocalKekProvider(kek, kek_id=kek_id)
    dek = os.urandom(DEK_LEN)
    kid = provider.kek_id.encode("utf-8")
    if not kid or len(kid) > 255:
        raise ValueError("kek_id must be 1–255 bytes")
    wrap_nonce, wrapped = provider.wrap(dek, kid)
    if len(wrapped) != WRAPPED_DEK_LEN:
        raise ValueError("wrapped DEK has unexpected length")
    data_nonce = os.urandom(NONCE_LEN)
    token = AESGCM(dek).encrypt(data_nonce, plaintext, None)
    return MAGIC_V2 + bytes([len(kid)]) + kid + wrap_nonce + wrapped + data_nonce + token


def decrypt_envelope(blob: bytes, kek: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not blob.startswith(MAGIC_V2):
        raise ValueError("artifact is not an SCENC2 envelope")
    offset = len(MAGIC_V2)
    kid_len = blob[offset]
    offset += 1
    kid = blob[offset : offset + kid_len]
    offset += kid_len
    wrap_nonce = blob[offset : offset + NONCE_LEN]
    offset += NONCE_LEN
    wrapped = blob[offset : offset + WRAPPED_DEK_LEN]
    offset += WRAPPED_DEK_LEN
    data_nonce = blob[offset : offset + NONCE_LEN]
    offset += NONCE_LEN
    token = blob[offset:]
    dek = LocalKekProvider(kek).unwrap(wrap_nonce, wrapped, kid)
    return AESGCM(dek).decrypt(data_nonce, token, None)


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if blob.startswith(MAGIC_V2):
        return decrypt_envelope(blob, key)
    if not blob.startswith(MAGIC):
        raise ValueError("artifact is not an encrypted Stage Coach payload")
    nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_LEN]
    token = blob[len(MAGIC) + NONCE_LEN :]
    return AESGCM(key).decrypt(nonce, token, None)


def is_encrypted_blob(blob: bytes) -> bool:
    return blob.startswith(MAGIC) or blob.startswith(MAGIC_V2)


def is_encrypted(path) -> bool:
    with open(path, "rb") as handle:
        return is_encrypted_blob(handle.read(len(MAGIC_V2)))


def write_encrypted_json(path, obj: object, key: Optional[bytes] = None, kek_id: str = "local") -> None:
    plaintext = (json.dumps(obj, indent=2) + "\n").encode("utf-8")
    Path(path).write_bytes(encrypt_envelope(plaintext, resolve_kek(key), kek_id=kek_id))


def load_json_object(path, key: Optional[bytes] = None) -> Optional[dict]:
    """Decrypt-on-read for SCENC1/SCENC2; plaintext JSON stays readable."""
    target = Path(path)
    if not target.is_file():
        return None
    raw = target.read_bytes()
    if is_encrypted_blob(raw):
        try:
            kek_or_key = resolve_kek(key) if raw.startswith(MAGIC_V2) else resolve_artifact_key(key)
            raw = decrypt_bytes(raw, kek_or_key)
        except Exception:
            return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None
