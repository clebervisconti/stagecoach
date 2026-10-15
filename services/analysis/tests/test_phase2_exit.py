"""Phase 2 exit: camera-setup N/A matrix, CPU bench (issue #54).

GPU seconds/media-minute and a 20-min P50 are not measured here (CPU-only CI).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "packages" / "scoring"))

from pipeline.accessibility import persist_accessibility
from pipeline.consent import VisionDecision
from pipeline.stages.fusion_scoring import run_fusion_scoring
from pipeline.stages.vision import run_vision_stage
from pipeline.vision.synthetic import scripted_events

from tests.test_fusion_scoring import PACKAGES, _write_inputs

TEST_KEY = bytes.fromhex("11" * 32)
VIDEO = VisionDecision(
    run_pose=True,
    run_hands=True,
    run_face_landmarks=True,
    run_expression_metrics=False,
    keep_raw_landmarks=False,
    skip_reason=None,
)
CONSENT_ON = {
    "policy_id": "1.0.0",
    "purposes": {
        "video_analysis": {"granted": True},
        "expression_analysis": {"granted": False},
        "keep_detailed_tracking": {"granted": False},
    },
}

BODY = ("gestures_body", "eye_contact")
TEXT_AUDIO = (
    "core_message",
    "structure",
    "storytelling",
    "audience_adaptation",
    "opening_close",
    "clarity",
    "impact",
    "pace_pausing",
    "vocal_variety",
    "fluency",
)


def _by_id(result: dict) -> dict:
    return {row["id"]: row for row in result["categories"]}


def _video_inputs(tmp_path: Path, setup: str) -> None:
    persist_accessibility(tmp_path, {})
    _write_inputs(tmp_path, with_content=True)
    (tmp_path / "consents.json").write_text(json.dumps(CONSENT_ON))
    run_vision_stage(
        output_dir=tmp_path,
        session_id="exit",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
        camera_setup=setup,
    )


def test_stage_fixture_body_applicable_slides_na(tmp_path: Path):
    _video_inputs(tmp_path, "stage")
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000154",
        output_dir=tmp_path,
        camera_setup="stage",
        packages_dir=PACKAGES,
    )
    cats = _by_id(result)
    for cid in TEXT_AUDIO:
        assert cats[cid]["applicable"] is True, cid
        assert cats[cid]["score"] is not None
        assert (cats[cid].get("confidence") or 0) > 0
    for cid in BODY:
        assert cats[cid]["applicable"] is True, cid
        assert cats[cid]["score"] is not None
    assert cats["visual_aids"]["applicable"] is False
    assert cats["facial_affect"]["applicable"] is False
    assert "expression" in (cats["facial_affect"]["na_reason"] or "").lower()


def test_to_camera_fixture_eye_contact_applicable(tmp_path: Path):
    _video_inputs(tmp_path, "to_camera")
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000155",
        output_dir=tmp_path,
        camera_setup="to_camera",
        packages_dir=PACKAGES,
    )
    cats = _by_id(result)
    assert cats["eye_contact"]["applicable"] is True
    assert cats["gestures_body"]["applicable"] is True
    assert cats["visual_aids"]["applicable"] is False


def test_screen_recording_fixture_slides_yes_body_na(tmp_path: Path):
    persist_accessibility(tmp_path, {})
    _write_inputs(tmp_path, with_content=True)
    (tmp_path / "consents.json").write_text(json.dumps(CONSENT_ON))
    (tmp_path / "visual_aids_metrics.json").write_text(
        json.dumps(
            {
                "slide_count": 3,
                "metrics": {
                    "va_words_per_slide_median": {
                        "value": 18.0,
                        "applicable": True,
                        "confidence": 0.8,
                    },
                    "va_reading_ratio": {"value": 0.15, "applicable": True, "confidence": 0.7},
                },
            }
        )
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000156",
        output_dir=tmp_path,
        camera_setup="screen_recording",
        packages_dir=PACKAGES,
    )
    cats = _by_id(result)
    assert cats["visual_aids"]["applicable"] is True
    assert cats["visual_aids"]["score"] is not None
    assert cats["eye_contact"]["applicable"] is False
    assert "face" in (cats["eye_contact"]["na_reason"] or "").lower() or "screen" in (
        cats["eye_contact"]["na_reason"] or ""
    ).lower()
    assert cats["gestures_body"]["applicable"] is False


def test_cpu_fusion_p50_ratio_under_1_5x(tmp_path: Path):
    """Scoring-only stand-in. Full ingest+ASR+vision on long media needs owner hardware."""
    _write_inputs(tmp_path, with_content=True)
    media_s = float(json.loads((tmp_path / "transcript.json").read_text())["duration"])
    started = time.perf_counter()
    run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000157",
        output_dir=tmp_path,
        camera_setup="audio_only",
        packages_dir=PACKAGES,
    )
    elapsed = time.perf_counter() - started
    ratio = elapsed / max(media_s, 0.001)
    report = {
        "media_s": media_s,
        "elapsed_s": elapsed,
        "ratio": ratio,
        "profile": "cpu",
        "scope": "fusion_scoring_only",
        "gpu": "unavailable_in_ci",
        "target_p50_ratio": 1.5,
    }
    (tmp_path / "phase2_bench.json").write_text(json.dumps(report, indent=2))
    assert ratio <= 1.5


def test_vision_cpu_seconds_per_media_minute(tmp_path: Path):
    frames = scripted_events()
    media_s = max(float(frames[-1].t) - float(frames[0].t), 0.001)
    started = time.perf_counter()
    run_vision_stage(
        output_dir=tmp_path,
        session_id="bench",
        decision=VIDEO,
        frames=frames,
        encryption_key=TEST_KEY,
        camera_setup="to_camera",
    )
    elapsed = time.perf_counter() - started
    sec_per_min = elapsed / (media_s / 60.0)
    report = {
        "vision_elapsed_s": elapsed,
        "media_s": media_s,
        "sec_per_media_minute_cpu": sec_per_min,
        "gpu": "unavailable_in_ci",
    }
    (tmp_path / "vision_bench.json").write_text(json.dumps(report, indent=2))
    assert sec_per_min > 0
    assert (tmp_path / "gesture_metrics.json").exists()
