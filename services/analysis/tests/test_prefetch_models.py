"""Prefetch must refuse a model whose SHA-256 does not match the pin."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.vision.models import MODEL_REGISTRY
from scripts.prefetch_models import YUNET_SHA256, require_sha


def test_prefetch_yunet_pin_matches_registry():
    row = next(item for item in MODEL_REGISTRY if item["filename"].endswith(".onnx"))
    assert row["sha256"] == YUNET_SHA256


def test_require_sha_rejects_mismatch(tmp_path: Path):
    path = tmp_path / "face_detection_yunet_2023mar.onnx"
    path.write_bytes(b"not-the-yunet-model")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        require_sha(path, YUNET_SHA256, path.name)
    assert path.exists() is False
