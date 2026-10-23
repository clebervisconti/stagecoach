"""Prefetch must refuse a model whose SHA-256 does not match the pin."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.vision.models import MODEL_REGISTRY
from scripts.prefetch_models import (
    FASTER_WHISPER_FILES,
    NLTK_PACKAGES,
    WAV2VEC2_EN_SHA256,
    WAV2VEC2_PT_FILES,
    WAV2VEC2_PT_REPO,
    YUNET_SHA256,
    require_sha,
)


def test_prefetch_yunet_pin_matches_registry():
    row = next(item for item in MODEL_REGISTRY if item["filename"].endswith(".onnx"))
    assert row["sha256"] == YUNET_SHA256


def test_prefetch_mediapipe_pins_match_registry():
    tasks = [row for row in MODEL_REGISTRY if str(row["filename"]).endswith(".task")]
    assert {row["filename"] for row in tasks} == {
        "pose_landmarker_full.task",
        "hand_landmarker.task",
        "face_landmarker.task",
    }
    for row in tasks:
        assert len(row["sha256"]) == 64


def test_prefetch_faster_whisper_and_nltk_pins():
    names = {name for name, _digest in FASTER_WHISPER_FILES}
    assert names == {"model.bin", "config.json", "tokenizer.json", "vocabulary.txt"}
    for _name, digest in FASTER_WHISPER_FILES:
        assert len(digest) == 64
    assert {row["name"] for row in NLTK_PACKAGES} == {"punkt", "punkt_tab"}
    for row in NLTK_PACKAGES:
        assert len(row["sha256"]) == 64


def test_prefetch_alignment_wav2vec2_pins():
    assert len(WAV2VEC2_EN_SHA256) == 64
    names = {name for name, _digest in WAV2VEC2_PT_FILES}
    assert "pytorch_model.bin" in names
    assert "config.json" in names
    assert "vocab.json" in names
    assert WAV2VEC2_PT_REPO.endswith("portuguese")
    for _name, digest in WAV2VEC2_PT_FILES:
        assert len(digest) == 64


def test_require_sha_rejects_mismatch(tmp_path: Path):
    path = tmp_path / "face_detection_yunet_2023mar.onnx"
    path.write_bytes(b"not-the-yunet-model")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        require_sha(path, YUNET_SHA256, path.name)
    assert path.exists() is False
