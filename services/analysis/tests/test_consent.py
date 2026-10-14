"""Vision consent gates: no processing without video_analysis (issue #37)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.consent import (
    decide_vision,
    persist_consent_snapshot,
    run_vision_if_allowed,
    video_category_na_reason,
)


def _snapshot(**granted: bool) -> dict:
    purposes = {
        name: {"granted": False, "granted_at": None, "revoked_at": None, "version": None}
        for name in (
            "video_analysis",
            "expression_analysis",
            "keep_detailed_tracking",
            "research_use",
            "benchmarks",
        )
    }
    for name, value in granted.items():
        purposes[name]["granted"] = value
    return {"policy_id": "1.0.0", "policy_version": "abc", "purposes": purposes}


def test_defaults_skip_all_vision():
    decision = decide_vision(None)
    assert decision.run_pose is False
    assert decision.run_hands is False
    assert decision.run_face_landmarks is False
    assert decision.run_expression_metrics is False
    assert decision.keep_raw_landmarks is False
    assert decision.skip_reason == "consent_denied:video_analysis"


def test_video_consent_does_not_enable_expression_or_raw_landmarks():
    decision = decide_vision(_snapshot(video_analysis=True))
    assert decision.run_pose is True
    assert decision.run_hands is True
    assert decision.run_face_landmarks is True
    assert decision.run_expression_metrics is False
    assert decision.keep_raw_landmarks is False


def test_expression_and_tracking_require_video_consent():
    decision = decide_vision(
        _snapshot(expression_analysis=True, keep_detailed_tracking=True)
    )
    assert decision.run_pose is False
    assert decision.run_expression_metrics is False
    assert decision.keep_raw_landmarks is False
    full = decide_vision(
        _snapshot(
            video_analysis=True,
            expression_analysis=True,
            keep_detailed_tracking=True,
        )
    )
    assert full.run_expression_metrics is True
    assert full.keep_raw_landmarks is True


def test_runner_is_not_called_without_video_consent():
    calls = []

    def runner(decision):
        calls.append(decision)
        return {"frames": 1}

    denied = run_vision_if_allowed(_snapshot(), runner)
    assert denied["status"] == "skipped"
    assert denied["called"] is False
    assert calls == []

    allowed = run_vision_if_allowed(_snapshot(video_analysis=True), runner)
    assert allowed["status"] == "ran"
    assert allowed["called"] is True
    assert len(calls) == 1
    assert calls[0].run_expression_metrics is False


def test_persist_snapshot_and_na_reasons(tmp_path: Path):
    snapshot = persist_consent_snapshot(tmp_path, _snapshot())
    written = json.loads((tmp_path / "consents.json").read_text())
    assert written["purposes"]["video_analysis"]["granted"] is False
    assert snapshot["decision"]["run_pose"] is False
    assert "consent is off" in video_category_na_reason("gestures_body", snapshot)
    assert "Expression analysis is off" in video_category_na_reason("facial_affect", snapshot)
    granted = persist_consent_snapshot(tmp_path, _snapshot(video_analysis=True, expression_analysis=True))
    assert "Vision stage was not run" in video_category_na_reason("gestures_body", granted)
    assert "visible face" in video_category_na_reason("facial_affect", granted)
