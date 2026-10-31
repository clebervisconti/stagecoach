"""E3-7: online_flow_v1 drops content judgments and never sends pictures."""

from __future__ import annotations

import json
from types import SimpleNamespace

from pipeline.screen.coaching import build_online_flow_payload, image_keys, run_online_flow


class Stub:
    def __init__(self, payloads: list):
        self.payloads = list(payloads)
        self.calls: list[dict] = []
        self.provider_name = "local"

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        data = self.payloads.pop(0) if self.payloads else {"observations": []}
        return SimpleNamespace(data=data)


def _good() -> dict:
    return {
        "observations": [
            {"title": "Pause at the cut", "detail": "Four cuts start mid-word.", "evidence_ids": ["scr_001"], "t": 12.0},
            {"title": "Name the next screen", "detail": "Two changes have no lead-in.", "evidence_ids": ["scr_002"], "t": 40.0},
            {"title": "Ask once", "detail": "The first ten minutes have no question.", "evidence_ids": ["ev_1"], "t": 8.0},
        ],
        "drills": [
            {"title": "Pause", "how": "Stop for a beat at each change.", "practice_time_min": 10, "targets_metric": "sf_clean_transition_ratio"},
            {"title": "Signpost", "how": "Say what the next screen is for.", "practice_time_min": 10, "targets_metric": "sf_signpost_ratio"},
            {"title": "Ask", "how": "Add one question in the opening.", "practice_time_min": 10, "targets_metric": "oe_interaction_prompts_per_10min"},
        ],
        "strengths": [{"title": "The screen stayed up.", "evidence_ids": ["scr_001"]}],
        "insufficient_evidence": False,
    }


def test_payload_has_no_picture_keys():
    payload = build_online_flow_payload(
        delivery_mode="webinar",
        language="en",
        screen_doc={
            "screen_visible_s": 180,
            "segments": [
                {
                    "id": "scr_001",
                    "t_start": 0,
                    "t_end": 30,
                    "type": "SLIDE",
                    "dwell_s": 30,
                    "ocr_word_count": 12,
                    "keyframe": "screen_keyframes/scr_001.jpg",
                    "flags": ["rushed"],
                    "narration": {"shared_terms": ["policy"]},
                }
            ],
            "metrics": [{"id": "sf_clean_transition_ratio", "value": 0.6, "applicable": True}],
            "events": [{"id": "ev_1", "kind": "dead_air", "t": 4, "dur_s": 6}],
        },
        transcript={"duration": 180, "segments": [{"id": "S0001", "start": 1, "end": 4, "text": "policy update"}]},
        camera={"framing_issues": ["eye_line_high"], "keyframe": "camera.jpg", "image": "nope"},
    )
    assert image_keys(payload) == []
    blob = json.dumps(payload)
    for key in ("image", "frame", "keyframe", "thumbnail", "base64"):
        assert f'"{key}"' not in blob
    assert "instructions" in payload
    assert payload["screens"][0]["narration"][0]["text"] == "policy update"


def test_content_judgment_is_dropped_and_absent_from_the_file(tmp_path, caplog):
    stub = Stub(
        [
            {
                "observations": [
                    {
                        "title": "Check the claim",
                        "detail": "your claim about X is incorrect",
                        "evidence_ids": ["scr_001"],
                        "t": 1,
                    }
                ],
                "drills": [],
                "strengths": [],
            },
            "your claim about X is incorrect",
        ]
    )
    with caplog.at_level("WARNING"):
        result = run_online_flow(
            output_dir=tmp_path,
            delivery_mode="webinar",
            language="en",
            client=stub,
        )
    document = json.loads((tmp_path / "online_flow.json").read_text(encoding="utf-8"))
    blob = json.dumps(document).lower()
    assert "incorrect" not in blob
    assert "content_judgment" in caplog.text
    assert document["fallback"] is True
    assert document["source"] == "template"
    assert document["content_judgment"] is False
    assert result["latency_s"] >= 0
    assert len(stub.calls) == 2
    assert stub.calls[0]["prompt_id"] == "online_flow_v1"


def test_good_answer_is_one_call_and_cached(tmp_path):
    stub = Stub([_good(), _good()])
    first = run_online_flow(output_dir=tmp_path, delivery_mode="online_talk", language="en", client=stub)
    second = run_online_flow(output_dir=tmp_path, delivery_mode="online_talk", language="en", client=stub)
    document = json.loads((tmp_path / "online_flow.json").read_text(encoding="utf-8"))
    assert first["fallback"] is False
    assert len(document["observations"]) == 3
    assert len(document["drills"]) == 3
    assert len(document["strengths"]) == 1
    assert len(stub.calls) == 1
    assert second["cached"] is True
    assert document["provider"] == "local"
    assert document["latency_s"] >= 0


def test_model_failure_still_records_latency(tmp_path):
    class Down:
        provider_name = "local"

        def generate_structured(self, **_kwargs):
            raise RuntimeError("model down")

    result = run_online_flow(output_dir=tmp_path, delivery_mode="recorded_video", language="en", client=Down())
    document = json.loads((tmp_path / "online_flow.json").read_text(encoding="utf-8"))
    assert result["fallback"] is True
    assert document["source"] == "template"
    assert document["latency_s"] >= 0
    assert "Metric:" in document["observations"][0]["title"]
    assert "incorrect" not in json.dumps(document).lower()
