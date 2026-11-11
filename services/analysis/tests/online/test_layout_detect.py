"""Layout detection on synthetic fixtures (scenarios 1 and empty)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.layout.detect import detect_layout
from pipeline.layout.faces import FaceDetection, FakeFaceDetector
from pipeline.layout.review import needs_layout_review
from pipeline.layout.tiles import iou
from pipeline.prepare import prepare_session

from .generate_online_fixtures import generate_one

FIXTURES = Path(__file__).parent / "fixtures"


def _iou_box(detected: dict, expected: dict) -> float:
    return iou(
        (detected["x"], detected["y"], detected["w"], detected["h"]),
        (expected["x"], expected["y"], expected["w"], expected["h"]),
    )


def test_yunet_detects_synthetic_face_and_classifies_composite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Real YuNet on the generated face — not FakeFaceDetector (LION O1 finding)."""
    monkeypatch.setenv("MEDIAPIPE_MODELS_DIR", str(tmp_path / "models"))
    video = generate_one("composite_pip_tr", tmp_path)
    manifest = json.loads((FIXTURES / "composite_pip_tr" / "manifest.json").read_text())
    layout = detect_layout(
        video,
        tmp_path / "yunet-job",
        duration_s=manifest["duration_s"],
        frame_width=manifest["width"],
        frame_height=manifest["height"],
        delivery_mode="webinar",
        preview_source=video,
    )
    segment = layout["segments"][0]
    assert segment["kind"] == "composite"
    roles = {row["role"]: row for row in segment["regions"]}
    assert "camera" in roles and "screen" in roles
    camera_truth = {"x": 0.8333, "y": 0.0, "w": 0.1667, "h": 0.2222}
    screen_truth = {"x": 0.0, "y": 0.0, "w": 0.8333, "h": 1.0}
    assert _iou_box(roles["camera"], camera_truth) >= 0.85
    assert _iou_box(roles["screen"], screen_truth) >= 0.85
    assert layout["confidence"] >= 0.8


def test_composite_auto_detect(tmp_path: Path):
    video = generate_one("composite_pip_tr", tmp_path)
    manifest = json.loads((FIXTURES / "composite_pip_tr" / "manifest.json").read_text())
    # Face sits inside the top-right tile of the 960-wide sample.
    detector = FakeFaceDetector(
        [FaceDetection(x=810, y=8, w=140, h=100, score=0.92)]
    )
    layout = detect_layout(
        video,
        tmp_path / "job",
        duration_s=manifest["duration_s"],
        frame_width=manifest["width"],
        frame_height=manifest["height"],
        delivery_mode="webinar",
        detector=detector,
        preview_source=video,
    )
    assert len(layout["segments"]) == 1
    segment = layout["segments"][0]
    assert segment["kind"] == "composite"
    roles = {row["role"]: row for row in segment["regions"]}
    assert "camera" in roles and "screen" in roles
    camera_truth = {
        "x": 0.8333,
        "y": 0.0,
        "w": 0.1667,
        "h": 0.2222,
    }
    screen_truth = {"x": 0.0, "y": 0.0, "w": 0.8333, "h": 1.0}
    assert _iou_box(roles["camera"], camera_truth) >= 0.85
    assert _iou_box(roles["screen"], screen_truth) >= 0.85
    assert layout["confidence"] >= 0.8


def test_review_shown_for_new_users():
    assert needs_layout_review(pref="when_unsure", confirmed_count=0, confidence=0.95) is True
    assert needs_layout_review(pref="when_unsure", confirmed_count=3, confidence=0.95) is False
    assert needs_layout_review(pref="when_unsure", confirmed_count=3, confidence=0.7) is True
    assert needs_layout_review(pref="never", confirmed_count=0, confidence=0.7) is False
    assert needs_layout_review(pref="never", confirmed_count=0, confidence=0.4) is True
    assert needs_layout_review(pref="always", confirmed_count=3, confidence=0.95) is True


def test_prepare_session_skips_layout_without_video_consent(tmp_path: Path):
    video = generate_one("composite_pip_tr", tmp_path)
    result = prepare_session(
        input_path=video,
        output_dir=tmp_path / "out-consent",
        session_id="11111111-1111-4111-8111-111111111112",
        delivery_mode="webinar",
        video_analysis_consent=False,
        confirmed_layout_count=0,
    )
    assert result["skip_layout"] is True
    assert result["audio_only"] is True
    assert result["reason"] == "consent_video_off"
    assert result["status"] == "processing"
    assert result["layout"] is None


def test_prepare_session_layout_review(tmp_path: Path):
    video = generate_one("composite_pip_tr", tmp_path)
    detector = FakeFaceDetector([FaceDetection(x=810, y=8, w=140, h=100, score=0.92)])
    result = prepare_session(
        input_path=video,
        output_dir=tmp_path / "out",
        session_id="11111111-1111-4111-8111-111111111111",
        delivery_mode="webinar",
        detector=detector,
        confirmed_layout_count=0,
    )
    assert result["status"] == "layout_review"
    assert result["layout"] is not None
    assert (tmp_path / "out" / "layout.json").is_file()
    assert (tmp_path / "out" / "ingest.json").is_file()


def test_screen_only_and_no_regions(tmp_path: Path):
    screen = generate_one("screen_only", tmp_path)
    layout = detect_layout(
        screen,
        tmp_path / "screen-job",
        duration_s=2.0,
        frame_width=1920,
        frame_height=1080,
        detector=FakeFaceDetector([]),
        preview_source=screen,
    )
    assert layout["segments"][0]["kind"] == "screen_full"
    roles = {row["role"] for row in layout["segments"][0]["regions"]}
    assert roles == {"screen"}

    from .generate_online_fixtures import write_no_regions

    dest = tmp_path / "no_regions" / "source.mp4"
    write_no_regions(dest, 1.0, 640, 360, 15)
    empty = detect_layout(
        dest,
        tmp_path / "empty-job",
        duration_s=1.0,
        frame_width=640,
        frame_height=360,
        detector=FakeFaceDetector([]),
        preview_source=dest,
    )
    assert empty["review_reason"] == "no_regions_found" or empty["segments"][0]["kind"] in {
        "no_video",
        "screen_full",
    }
