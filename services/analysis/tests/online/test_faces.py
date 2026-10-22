"""YuNet registry + FakeFaceDetector (E0-2)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.layout.faces import (
    YUNET_FILENAME,
    FaceDetection,
    FakeFaceDetector,
    YuNetFaceDetector,
    yunet_registry_row,
)
from pipeline.vision.models import MODEL_REGISTRY, ensure_models


def test_yunet_is_registered_with_sha_and_mit_licence():
    row = yunet_registry_row()
    assert row["filename"] == YUNET_FILENAME
    assert row["license"] == "MIT"
    assert len(row["sha256"]) == 64
    assert row["used_by"] == "layout"
    assert any(item["component"] == "layout_face" for item in MODEL_REGISTRY)


def test_ensure_models_skips_yunet_by_default(tmp_path: Path):
    paths = ensure_models(tmp_path)
    assert YUNET_FILENAME not in paths


def test_fake_face_detector_returns_scripted_boxes():
    box = FaceDetection(x=10, y=20, w=40, h=50, score=0.91, landmarks=[(12.0, 22.0)])
    detector = FakeFaceDetector([box])
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    got = detector.detect(frame)
    assert len(got) == 1
    assert got[0].w == 40
    assert got[0].as_dict()["score"] == 0.91


@pytest.mark.real_faces
def test_yunet_detects_face_on_cached_cc0_frame():
    cache = Path(__file__).parent / "cache" / "cc0_face.jpg"
    if not cache.is_file():
        pytest.skip("CC0 face cache is absent")
    import cv2

    frame = cv2.imread(str(cache))
    assert frame is not None
    detector = YuNetFaceDetector()
    faces = detector.detect(frame)
    assert len(faces) >= 1
