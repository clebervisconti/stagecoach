"""Partial_ready events and vision-failure N/A for categories 12–14 (issue #46)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "packages" / "scoring"))

import jsonschema
from pipeline.partial import (
    BODY_CATEGORIES,
    VISION_FAILED_NA,
    VISION_FAILED_WARNING,
    done_event,
    partial_ready_event,
    scored_category_ids,
    stage_event,
    vision_failed_na_reason,
    write_vision_status,
)
from pipeline.stages.fusion_scoring import run_fusion_scoring
from test_fusion_scoring import PACKAGES, SCHEMA, _write_inputs


def _granted_consents(tmp_path: Path) -> None:
    (tmp_path / "consents.json").write_text(
        json.dumps(
            {
                "policy_id": "1.0.0",
                "purposes": {
                    "video_analysis": {"granted": True},
                    "expression_analysis": {"granted": True},
                    "keep_detailed_tracking": {"granted": False},
                },
            }
        ),
        encoding="utf-8",
    )


def test_stage_and_partial_ready_match_spec_shapes() -> None:
    stage = stage_event(
        "job-1",
        "audio_features",
        "succeeded",
        session_id="sess-1",
        pct=82,
        message="Audio measurements ready",
    )
    assert stage["type"] == "stage"
    assert stage["job_id"] == "job-1"
    assert stage["session_id"] == "sess-1"
    assert stage["stage"] == "audio_features"
    assert stage["status"] == "succeeded"
    ready = partial_ready_event(
        "job-1",
        ["pace_pausing", "fluency", "vocal_variety"],
        session_id="sess-1",
    )
    assert ready["type"] == "partial_ready"
    assert ready["categories"] == ["pace_pausing", "fluency", "vocal_variety"]
    done = done_event("job-1", "partial", session_id="sess-1")
    assert done["type"] == "done"
    assert done["status"] == "partial"


def test_scored_category_ids_omit_na_rows() -> None:
    ids = scored_category_ids(
        {
            "categories": [
                {"id": "pace_pausing", "applicable": True, "score": 70},
                {"id": "gestures_body", "applicable": False, "score": None},
                {"id": "fluency", "applicable": True, "score": 0},
            ]
        }
    )
    assert ids == ["pace_pausing", "fluency"]


def test_vision_failure_marks_body_categories_na(tmp_path: Path) -> None:
    _write_inputs(tmp_path, with_content=True)
    _granted_consents(tmp_path)
    write_vision_status(
        tmp_path, "failed", error={"type": "RuntimeError", "message": "boom"}
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000046",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        slot_min=4,
        camera_setup="to_camera",
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
        content_path=tmp_path / "content.json",
    )
    jsonschema.validate(instance=result, schema=SCHEMA)
    by_id = {c["id"]: c for c in result["categories"]}
    for cid in BODY_CATEGORIES:
        assert by_id[cid]["applicable"] is False
        assert by_id[cid]["score"] is None
        assert by_id[cid]["na_reason"] == VISION_FAILED_NA[cid]
    assert "gb_gesture_activity_ratio" not in {m["id"] for m in result["metrics"]}
    assert "ec_audience_facing_ratio" not in {m["id"] for m in result["metrics"]}
    assert "fa_smile_presence_ratio" not in {m["id"] for m in result["metrics"]}
    assert VISION_FAILED_WARNING in (result.get("quality") or {}).get("warnings", [])
    scored = scored_category_ids(result)
    assert "pace_pausing" in scored
    assert "fluency" in scored
    assert "vocal_variety" in scored
    assert "gestures_body" not in scored
    assert "eye_contact" not in scored
    assert "facial_affect" not in scored


def test_vision_failure_does_not_override_consent_off(tmp_path: Path) -> None:
    _write_inputs(tmp_path, with_content=False, short=True)
    write_vision_status(tmp_path, "failed", error={"message": "boom"})
    (tmp_path / "consents.json").write_text(
        json.dumps(
            {
                "policy_id": "1.0.0",
                "purposes": {
                    "video_analysis": {"granted": False},
                    "expression_analysis": {"granted": False},
                    "keep_detailed_tracking": {"granted": False},
                },
            }
        ),
        encoding="utf-8",
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000047",
        output_dir=tmp_path,
        camera_setup="to_camera",
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert "consent is off" in (by_id["gestures_body"]["na_reason"] or "")
    assert "Expression analysis is off" in (by_id["facial_affect"]["na_reason"] or "")


def test_vision_failed_reason_only_when_status_failed(tmp_path: Path) -> None:
    assert vision_failed_na_reason(tmp_path, "gestures_body") is None
    write_vision_status(tmp_path, "succeeded")
    assert vision_failed_na_reason(tmp_path, "gestures_body") is None
    write_vision_status(tmp_path, "failed")
    assert (
        vision_failed_na_reason(tmp_path, "gestures_body")
        == VISION_FAILED_NA["gestures_body"]
    )
