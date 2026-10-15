"""SCENC2 envelope encryption for derived biometric JSON (issue #50)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipeline.vision.crypto import (
    MAGIC,
    MAGIC_V2,
    LocalKekProvider,
    MissingArtifactKeyError,
    OwnerKmsKekProvider,
    decrypt_bytes,
    decrypt_envelope,
    encrypt_bytes,
    encrypt_envelope,
    is_encrypted,
    load_json_object,
    resolve_kek,
    write_encrypted_json,
)

KEK = bytes.fromhex("22" * 32)
OTHER = bytes.fromhex("33" * 32)


def test_envelope_roundtrip_uses_wrapped_dek():
    plaintext = b'{"fa_smile_presence_ratio": 0.4}'
    blob = encrypt_envelope(plaintext, KEK, kek_id="local")
    assert blob.startswith(MAGIC_V2)
    assert MAGIC not in blob[:6]
    assert decrypt_envelope(blob, KEK) == plaintext
    with pytest.raises(Exception):
        decrypt_envelope(blob, OTHER)


def test_decrypt_bytes_reads_scenc1_and_scenc2():
    key = bytes.fromhex("11" * 32)
    v1 = encrypt_bytes(b"legacy-parquet", key)
    v2 = encrypt_envelope(b"json-payload", key)
    assert decrypt_bytes(v1, key) == b"legacy-parquet"
    assert decrypt_bytes(v2, key) == b"json-payload"


def test_write_and_load_encrypted_json(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STAGECOACH_ARTIFACT_KEY", KEK.hex())
    monkeypatch.delenv("STAGECOACH_KEK", raising=False)
    path = tmp_path / "expression_metrics.json"
    payload = {"emotion_inference": False, "metrics": {"fa_smile_presence_ratio": 0.2}}
    write_encrypted_json(path, payload, KEK)
    assert is_encrypted(path)
    assert path.read_bytes()[:6] == MAGIC_V2
    assert b"fa_smile_presence_ratio" not in path.read_bytes()
    assert load_json_object(path) == payload
    assert load_json_object(path, KEK)["metrics"]["fa_smile_presence_ratio"] == 0.2


def test_load_json_object_reads_plaintext(tmp_path: Path):
    path = tmp_path / "plain.json"
    path.write_text('{"ok": true}\n', encoding="utf-8")
    assert load_json_object(path) == {"ok": True}


def test_local_kek_falls_back_to_artifact_key(monkeypatch):
    monkeypatch.delenv("STAGECOACH_KEK", raising=False)
    monkeypatch.setenv("STAGECOACH_ARTIFACT_KEY", KEK.hex())
    assert resolve_kek() == KEK
    monkeypatch.delenv("STAGECOACH_ARTIFACT_KEY", raising=False)
    with pytest.raises(MissingArtifactKeyError):
        resolve_kek()


def test_kms_provider_is_not_selected_without_owner_decision():
    provider = OwnerKmsKekProvider()
    with pytest.raises(RuntimeError, match="owner decision"):
        provider.wrap(os.urandom(32), b"local")
    local = LocalKekProvider(KEK)
    nonce, wrapped = local.wrap(b"d" * 32, b"local")
    assert local.unwrap(nonce, wrapped, b"local") == b"d" * 32
