"""Body tab and Slides tab view models (issue #48, SPEC §8.7)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.body_slides import (
    build_body,
    build_slides_tab,
    keyframe_path,
    persist_body_slides,
)
from pipeline.vision.gaze import yaw_histogram_bins
from pipeline.vision.gestures import wrist_space_density


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_wrist_space_density_counts_visible_wrists() -> None:
    rows = [
        {
            "wrist_l_x": -0.8,
            "wrist_l_y": -0.8,
            "wrist_l_vis": 0.9,
            "wrist_r_x": 0.8,
            "wrist_r_y": -0.8,
            "wrist_r_vis": 0.9,
        },
        {
            "wrist_l_x": -0.8,
            "wrist_l_y": -0.8,
            "wrist_l_vis": 0.1,
            "wrist_r_x": 0.8,
            "wrist_r_y": -0.8,
            "wrist_r_vis": 0.1,
        },
    ]
    grid = wrist_space_density(rows)
    assert grid["samples"] == 2
    assert sum(grid["cells"]) == 2
    assert grid["cols"] == 8 and grid["rows"] == 6


def test_yaw_histogram_bins_empty_without_samples() -> None:
    assert yaw_histogram_bins([], lo=-35, hi=35, bin_deg=10) == []
    bins = yaw_histogram_bins([-20.0, -18.0, 10.0], lo=-35, hi=35, bin_deg=10)
    assert sum(b["count"] for b in bins) == 3
    assert all("center" in b for b in bins)


def test_build_body_from_artifacts(tmp_path: Path) -> None:
    _write(
        tmp_path / "gesture_metrics.json",
        {
            "activity_windows": [
                {"start": 0.0, "value": 0.8},
                {"start": 1.0, "value": 0.1},
            ],
            "space_density": {"cols": 8, "rows": 6, "samples": 2, "cells": [1, 0, 1]},
            "metrics": {
                "gb_sway_index": {
                    "value": 0.12,
                    "applicable": True,
                    "unit": "shoulder_widths_sd",
                }
            },
        },
    )
    _write(
        tmp_path / "gaze_metrics.json",
        {
            "yaw_histogram": [{"center": -10, "count": 4}],
            "metrics": {"ec_audience_facing_ratio": {"value": 0.7, "applicable": True}},
        },
    )
    _write(
        tmp_path / "vision_events.json",
        {
            "events": [
                {"type": "self_adaptor", "t_start": 2.0, "t_end": 3.0},
                {"type": "notes_down", "t_start": 4.0, "t_end": 6.5},
                {"type": "smile", "t_start": 1.0, "t_end": 1.4},
            ]
        },
    )
    _write(
        tmp_path / "vision_quality.json",
        {
            "person_visible_ratio": 0.9,
            "face_visible_ratio": 0.8,
            "mean_face_height_px": 92.0,
            "mean_person_height_px": 240.0,
            "camera_setup": {"declared": "to_camera", "detected": "to_camera"},
        },
    )
    _write(
        tmp_path / "expression_metrics.json",
        {"expressivity_windows": [{"start": 0.0, "value": 0.2}]},
    )
    _write(
        tmp_path / "consents.json",
        {"purposes": {"expression_analysis": {"granted": False}}},
    )
    body = persist_body_slides(tmp_path, duration_s=12)[0]
    assert body["available"] is True
    assert len(body["heat"]) == 2
    assert body["sway"]["applicable"] is True
    assert body["sway"]["value"] == 0.12
    assert body["yaw_histogram"][0]["count"] == 4
    assert body["notes_down"][0]["t_start"] == 4.0
    assert all(e["type"] != "smile" for e in body["events"])
    assert body["expressivity"]["available"] is False
    assert body["expressivity"]["points"] == []
    assert body["quality"]["mean_face_height_px"] == 92.0
    assert body["emotion_inference"] is False
    assert (tmp_path / "body.json").is_file()


def test_expressivity_only_with_opt_in(tmp_path: Path) -> None:
    _write(
        tmp_path / "expression_metrics.json",
        {"expressivity_windows": [{"start": 0.0, "value": 0.3}]},
    )
    _write(
        tmp_path / "consents.json",
        {"purposes": {"expression_analysis": {"granted": True}}},
    )
    body = build_body(tmp_path, duration_s=4)
    assert body["expressivity"]["available"] is True
    assert body["expressivity"]["points"][0]["value"] == 0.3


def test_slides_tab_does_not_invent_glance_or_titles(tmp_path: Path) -> None:
    _write(
        tmp_path / "slides.json",
        {
            "slides": [
                {
                    "index": 1,
                    "t_start": 0.0,
                    "t_end": 10.0,
                    "dwell_s": 10.0,
                    "title": "Roadmap",
                    "word_count": 18,
                    "reading_overlap": 0.25,
                    "keyframe": str(tmp_path / "keyframes" / "slide_001.jpg"),
                }
            ]
        },
    )
    _write(
        tmp_path / "vision_events.json",
        {"events": [{"type": "screen_turn", "t_start": 2.0, "t_end": 4.0}]},
    )
    (tmp_path / "keyframes").mkdir()
    (tmp_path / "keyframes" / "slide_001.jpg").write_bytes(b"jpeg")
    slides = persist_body_slides(tmp_path)[1]
    row = slides["slides"][0]
    assert row["title_type"] == "topic"
    assert row["glance_level"] is None
    assert row["suggested_title"] is None
    assert row["suggestion_source"] is None
    assert row["facing_screen_s"] == 2.0
    assert row["reading_overlap"] == 0.25
    assert row["has_keyframe"] is True
    assert keyframe_path(tmp_path, 1).name == "slide_001.jpg"
    assert keyframe_path(tmp_path, 9) is None


def test_slides_ai_suggestion_only_from_slides_v1(tmp_path: Path) -> None:
    _write(
        tmp_path / "slides.json",
        {"slides": [{"index": 1, "title": "Q3", "word_count": 8, "dwell_s": 5}]},
    )
    _write(
        tmp_path / "slides_v1.json",
        {
            "slides": [
                {
                    "index": 1,
                    "title_type": "topic",
                    "glance_level": 3,
                    "suggested_assertion_title": "Q3 revenue grew 12%.",
                    "issues": [],
                    "insufficient_evidence": False,
                }
            ]
        },
    )
    slides = build_slides_tab(tmp_path)
    assert slides["slides"][0]["suggested_title"] == "Q3 revenue grew 12%."
    assert slides["slides"][0]["suggestion_source"] == "ai"
    assert slides["slides"][0]["glance_level"] == 3
    assert slides["ai_suggestions"] is True


def test_missing_artifacts_stay_empty(tmp_path: Path) -> None:
    body, slides = persist_body_slides(tmp_path, duration_s=8)
    assert body["available"] is False
    assert body["heat"] == []
    assert body["events"] == []
    assert body["sway"]["applicable"] is False
    assert slides["available"] is False
    assert slides["slides"] == []
