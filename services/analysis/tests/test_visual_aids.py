"""Category 8 visual aids (issue #44) on synthetic screen-recording media."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "packages" / "scoring"))

from pipeline.slides.glance import MAX_IMAGES, run_slides_v1
from pipeline.slides.visual_aids import UNITS, compute_visual_aids_metrics, headline_type
from pipeline.stages.fusion_scoring import run_fusion_scoring
from pipeline.stages.slides import run_slides_stage

PACKAGES = Path(__file__).parents[3] / "packages"
SCORING_YAML = PACKAGES / "scoring-config" / "v1.0.0" / "scoring.yaml"


def _pptx(path: Path) -> None:
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "We shipped the feature this quarter"
    slide.placeholders[1].text = "Revenue grew after launch\nChurn fell in the same window"
    prs.save(str(path))


def _screen_recording(path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0xEEEEEE:s=640x360:d=4:r=10",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x2266AA:s=640x360:d=4:r=10",
        "-filter_complex",
        "[0:v][1:v]concat=n=2:v=1:a=0",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def test_units_match_scoring_yaml():
    config = yaml.safe_load(SCORING_YAML.read_text())
    for metric_id, spec in config["categories"]["visual_aids"]["metrics"].items():
        assert metric_id in UNITS
        assert spec["unit"] == UNITS[metric_id]


def test_headline_heuristic_and_reading_ratio():
    assert headline_type("We shipped the feature this quarter") == "assertion"
    assert headline_type("Agenda") == "topic"
    slides = {
        "slides": [
            {
                "index": 1,
                "title": "We shipped the feature this quarter",
                "text": "We shipped the feature this quarter revenue grew after launch churn fell",
                "word_count": 14,
                "t_start": 0,
                "t_end": 10,
                "dwell_s": 10,
                "reading_overlap": 0.8,
            },
            {
                "index": 2,
                "title": "Agenda",
                "text": "Agenda next steps",
                "word_count": 3,
                "t_start": 10,
                "t_end": 20,
                "dwell_s": 10,
                "reading_overlap": 0.0,
            },
        ]
    }
    payload = compute_visual_aids_metrics(slides, duration_s=20)
    assert payload is not None
    assert payload["metrics"]["va_reading_ratio"]["value"] == pytest.approx(0.5)
    assert payload["metrics"]["va_dense_slide_ratio"]["value"] == 0.0
    assert payload["metrics"]["va_glance_llm"]["applicable"] is False


def test_deck_only_scales_reading_confidence():
    slides = {
        "slides": [
            {
                "index": 1,
                "title": "We shipped the feature this quarter",
                "text": "We shipped the feature this quarter after the launch",
                "word_count": 10,
                "t_start": None,
                "dwell_s": None,
            }
        ]
    }
    transcript = {
        "segments": [
            {"start": 0, "end": 8, "text": "We shipped the feature this quarter after the launch today"}
        ]
    }
    payload = compute_visual_aids_metrics(slides, transcript=transcript, duration_s=8)
    assert payload["deck_only"] is True
    assert payload["metrics"]["va_reading_ratio"]["confidence"] <= 0.6
    assert payload["metrics"]["va_screen_facing_s_per_min"]["applicable"] is False


def test_none_without_slides():
    assert compute_visual_aids_metrics({"slides": []}) is None


def test_slides_v1_caps_at_20_and_uses_client():
    calls = {}

    class Client:
        def generate_structured(self, prompt_id, inputs, schema, temperature=None):
            calls["n"] = len(inputs["slides"])
            calls["prompt_id"] = prompt_id
            assert len(inputs["slides"]) <= MAX_IMAGES
            return SimpleNamespace(
                data={
                    "insufficient_evidence": False,
                    "slides": [
                        {
                            "index": 1,
                            "title_type": "assertion",
                            "one_idea": True,
                            "glance_level": 4,
                            "issues": [],
                            "insufficient_evidence": False,
                        }
                    ],
                }
            )

    many = [{"index": i, "title": "T", "word_count": 5, "keyframe": None} for i in range(1, 25)]
    out = run_slides_v1(many, client=Client())
    assert calls["prompt_id"] == "slides_v1"
    assert calls["n"] == 20
    assert out["slides"][0]["glance_level"] == 4
    assert out["image_count"] <= 20


def test_golden_screen_recording_scores_visual_aids(tmp_path: Path):
    video = tmp_path / "screen.mp4"
    deck = tmp_path / "deck.pptx"
    _screen_recording(video)
    _pptx(deck)
    transcript = {
        "language": "en",
        "duration": 8.0,
        "segments": [
            {
                "id": "S0001",
                "start": 0,
                "end": 8,
                "text": "We shipped the feature this quarter revenue grew after launch",
            }
        ],
    }
    (tmp_path / "transcript.json").write_text(json.dumps(transcript))
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(json.dumps({"duration_s": 8}))
    result = run_slides_stage(
        output_dir=tmp_path,
        session_id="s",
        video_path=video,
        deck_path=deck,
        camera_setup="screen_recording",
        language="en",
        transcript=transcript,
        is_screen_recording=True,
    )
    assert result.skipped is False
    va = json.loads((tmp_path / "visual_aids_metrics.json").read_text())
    assert va["slide_count"] >= 1
    assert "va_words_per_slide_median" in va["metrics"]
    fusion = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000144",
        output_dir=tmp_path,
        camera_setup="screen_recording",
        packages_dir=PACKAGES,
    )
    by_id = {c["id"]: c for c in fusion["categories"]}
    assert by_id["visual_aids"]["applicable"] is True
    assert by_id["visual_aids"]["score"] is not None
    present = {m["id"] for m in fusion["metrics"]}
    assert "va_words_per_slide_median" in present
    assert "va_reading_ratio" in present
    # No live LLM in CI: glance stays N/A rather than a made-up level.
    assert "va_glance_llm" not in present
