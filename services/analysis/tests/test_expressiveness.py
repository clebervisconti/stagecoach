"""Category 14 facial expressiveness (issue #42, D8). Opt-in; no emotion labels."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "packages" / "scoring"))

from pipeline.consent import VisionDecision
from pipeline.stages.fusion_scoring import run_fusion_scoring
from pipeline.stages.report import FORBIDDEN, run_report_stage
from pipeline.stages.vision import run_vision_stage
from pipeline.vision.crypto import MAGIC_V2, load_json_object
from pipeline.vision.expressiveness import attach_incongruence
from pipeline.vision.synthetic import scripted_events

TEST_KEY = bytes.fromhex("11" * 32)
os.environ.setdefault("STAGECOACH_ARTIFACT_KEY", TEST_KEY.hex())
PACKAGES = Path(__file__).parents[3] / "packages"
VIDEO = VisionDecision(
    run_pose=True,
    run_hands=True,
    run_face_landmarks=True,
    run_expression_metrics=True,
    keep_raw_landmarks=False,
    skip_reason=None,
)
ON = {
    "policy_id": "1.0.0",
    "purposes": {
        "video_analysis": {"granted": True},
        "expression_analysis": {"granted": True},
        "keep_detailed_tracking": {"granted": False},
    },
}
OFF = {
    "policy_id": "1.0.0",
    "purposes": {
        "video_analysis": {"granted": True},
        "expression_analysis": {"granted": False},
        "keep_detailed_tracking": {"granted": False},
    },
}

BANNED = re.compile(
    r"\b(happy|sad|angry|anxious|fearful|joyful|stressed|stress|engagement|"
    r"authenticity|nervous|feliz|triste|ansioso|estresse|engajamento|autenticidade)\b",
    re.IGNORECASE,
)


def _transcript(*texts: str) -> dict:
    segs = []
    t = 0.0
    for i, text in enumerate(texts):
        segs.append({"id": f"S{i+1:04d}", "start": t, "end": t + 3.0, "text": text})
        t += 3.0
    return {"language": "en", "duration": t, "segments": segs, "words": []}


def test_expression_metrics_written_only_with_consent(tmp_path: Path):
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    expr_path = tmp_path / "expression_metrics.json"
    assert expr_path.read_bytes()[:6] == MAGIC_V2
    payload = load_json_object(expr_path, TEST_KEY)
    assert payload is not None
    assert payload["emotion_inference"] is False
    assert "fa_smile_presence_ratio" in payload["metrics"]
    assert "fa_expressivity_index" in payload["metrics"]
    assert BANNED.search(json.dumps(payload)) is None

    off = VisionDecision(
        run_pose=True,
        run_hands=True,
        run_face_landmarks=True,
        run_expression_metrics=False,
        keep_raw_landmarks=False,
        skip_reason=None,
    )
    dest = tmp_path / "off"
    run_vision_stage(
        output_dir=dest,
        session_id="s",
        decision=off,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    assert not (dest / "expression_metrics.json").exists()


def test_facial_affect_scored_only_when_opted_in(tmp_path: Path):
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    (tmp_path / "consents.json").write_text(json.dumps(ON))
    (tmp_path / "transcript.json").write_text(json.dumps(_transcript("Welcome to the briefing.")))
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(json.dumps({"duration_s": 5, "voiced_s": 4}))
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000042",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["facial_affect"]["applicable"] is True
    assert by_id["facial_affect"]["score"] is not None
    present = {m["id"] for m in result["metrics"]}
    assert "fa_smile_presence_ratio" in present
    assert "fa_expressivity_index" in present
    assert BANNED.search(json.dumps(result["categories"])) is None
    report = run_report_stage(output_dir=tmp_path, analysis=result, packages_dir=PACKAGES)
    assert FORBIDDEN.search(json.dumps(report["insights"])) is None


def test_default_off_keeps_category_14_na(tmp_path: Path):
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    (tmp_path / "consents.json").write_text(json.dumps(OFF))
    (tmp_path / "transcript.json").write_text(json.dumps(_transcript("Hello.")))
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(json.dumps({"duration_s": 5}))
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000043",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["facial_affect"]["applicable"] is False
    assert "Expression analysis is off" in (by_id["facial_affect"]["na_reason"] or "")
    assert "fa_smile_presence_ratio" not in {m["id"] for m in result["metrics"]}


def test_incongruence_flag_is_observation_not_emotion():
    events = [{"type": "smile", "t_start": 0.0, "t_end": 2.5}]
    payload = {
        "metrics": {"fa_congruence": {}},
        "emotion_inference": False,
    }
    out = attach_incongruence(
        payload,
        events,
        _transcript("The layoff starts next week."),
        10.0,
    )
    row = out["metrics"]["fa_congruence"]
    assert row["applicable"] is True
    assert row["incongruence_flags_per_10min"] > 0
    assert row["value"] < 5
    blob = json.dumps(row).lower()
    assert "happy" not in blob and "sad" not in blob
    assert "observation" in blob


def test_no_ser_models_in_requirements():
    req = (Path(__file__).parent.parent / "requirements.txt").read_text().lower()
    assert "opensmile" not in req
    assert "ser" not in req.split()
    assert "emotion-recognition" not in req
    assert "wav2vec2-emotion" not in req


def test_source_and_ui_have_no_forbidden_emotion_labels():
    roots = [
        Path(__file__).parent.parent / "pipeline" / "vision",
        Path(__file__).parent.parent / "pipeline" / "stages",
        PACKAGES / "consent" / "v1.json",
    ]
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            assert "import openface" not in lowered
            assert "emotion_classifier" not in lowered
            assert "you were happy" not in lowered
            assert "speech emotion" not in lowered
