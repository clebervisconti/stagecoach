"""Video-synced timeline lanes (issue #47, SPEC §8.4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.timeline import LANE_IDS, build_timeline, persist_timeline, sprite_path


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_lane_ids_match_spec() -> None:
    assert LANE_IDS == (
        "sections",
        "slides",
        "fillers",
        "long_pauses",
        "rushing",
        "monotone",
        "gestures",
        "audience_facing",
        "smiles",
        "clt_story",
        "qa",
    )


def test_build_timeline_from_artifacts(tmp_path: Path) -> None:
    _write(
        tmp_path / "transcript.json",
        {
            "duration": 40.0,
            "segments": [
                {
                    "id": "S0001",
                    "start": 0.0,
                    "end": 12.0,
                    "text": "Um hello",
                    "words": [
                        {
                            "word": "Um",
                            "start": 0.2,
                            "end": 0.5,
                            "tags": ["filler_sound"],
                        },
                        {"word": "hello", "start": 0.6, "end": 1.0},
                    ],
                },
                {"id": "S0002", "start": 12.0, "end": 24.0, "text": "story beat"},
                {"id": "S0003", "start": 24.0, "end": 36.0, "text": "question"},
            ],
        },
    )
    _write(
        tmp_path / "content.json",
        {
            "outline": {
                "sections": [
                    {"title": "Open", "start_seg": "S0001", "end_seg": "S0001"}
                ]
            },
            "story_impact": {
                "stories": [{"start_seg": "S0002", "end_seg": "S0002"}],
                "clt_instances": [
                    {
                        "type": "rhetorical_question",
                        "seg_id": "S0001",
                        "quote": "What if?",
                    }
                ],
            },
            "qa": {"pairs": [{"q_seg": "S0003", "a_seg": "S0003"}]},
        },
    )
    _write(
        tmp_path / "slides.json",
        {"slides": [{"index": 1, "t_start": 0.0, "t_end": 10.0, "title": "Title"}]},
    )
    _write(
        tmp_path / "pauses.json",
        {"pauses": [{"kind": "long", "duration": 3.4, "start": 8.0, "end": 11.4}]},
    )
    _write(
        tmp_path / "audio_metrics.json",
        {
            "duration_s": 40.0,
            "pvq_windows": [{"start": 20.0, "end": 30.0, "value": 0.04}],
        },
    )
    _write(
        tmp_path / "gesture_metrics.json",
        {"activity_windows": [{"start": 5.0, "value": 0.9}]},
    )
    _write(
        tmp_path / "vision_events.json",
        {
            "events": [
                {"type": "gesture_stroke", "t_start": 6.0, "t_end": 6.4},
                {"type": "smile", "t_start": 7.0, "t_end": 8.0},
            ]
        },
    )
    _write(
        tmp_path / "series_gaze.json",
        {"points": [{"t": 0, "value": 1}, {"t": 1, "value": 1}, {"t": 2, "value": 0}]},
    )
    _write(
        tmp_path / "consents.json",
        {
            "purposes": {
                "expression_analysis": {"granted": True},
                "video_analysis": {"granted": True},
            }
        },
    )
    (tmp_path / "sprites").mkdir()
    (tmp_path / "sprites" / "sprite_0000.jpg").write_bytes(b"jpeg")

    payload = persist_timeline(tmp_path, duration_s=40)
    assert payload["duration_s"] == 40.0
    assert payload["sprite_interval_s"] == 5
    assert payload["sprite_count"] == 1
    by_id = {lane["id"]: lane for lane in payload["lanes"]}
    assert list(by_id) == list(LANE_IDS)
    assert by_id["sections"]["items"][0]["label"] == "Open"
    assert by_id["slides"]["items"][0]["label"] == "Title"
    assert by_id["fillers"]["items"][0]["label"] == "Um"
    assert by_id["long_pauses"]["items"][0]["kind"] == "long_pause"
    assert by_id["monotone"]["items"][0]["kind"] == "monotone"
    assert by_id["gestures"]["items"]
    assert by_id["audience_facing"]["items"][0]["kind"] == "facing"
    assert by_id["smiles"]["available"] is True
    assert by_id["smiles"]["opt_in"] is True
    assert by_id["smiles"]["items"][0]["kind"] == "smile"
    assert by_id["clt_story"]["items"]
    assert by_id["qa"]["items"][0]["kind"] == "qa"
    assert sprite_path(tmp_path, 0) is not None
    assert sprite_path(tmp_path, 0).name == "sprite_0000.jpg"
    assert sprite_path(tmp_path, 12) is None


def test_smiles_unavailable_without_expression_opt_in(tmp_path: Path) -> None:
    _write(tmp_path / "transcript.json", {"duration": 5, "segments": []})
    _write(
        tmp_path / "vision_events.json",
        {"events": [{"type": "smile", "t_start": 1.0, "t_end": 2.0}]},
    )
    _write(
        tmp_path / "consents.json",
        {"purposes": {"expression_analysis": {"granted": False}}},
    )
    payload = build_timeline(tmp_path, duration_s=5)
    smiles = next(lane for lane in payload["lanes"] if lane["id"] == "smiles")
    assert smiles["available"] is False
    assert smiles["items"] == []


def test_missing_artifacts_do_not_invent_spans(tmp_path: Path) -> None:
    payload = build_timeline(tmp_path, duration_s=10)
    for lane in payload["lanes"]:
        assert lane["items"] == []
    assert payload["sprite_count"] == 0
