"""E3-2: stable cuts, scroll suppression, and a small popup."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.screen.activity import activity_from_grays
from pipeline.screen.transitions import accept_transitions, transition_f1
from tests.online.screen_frames import scroll_frames, slide_sequence

MANIFEST = Path(__file__).parent / "fixtures" / "screen_flow_manifest.json"


def test_slide_cuts_meet_f1():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = activity_from_grays(slide_sequence())
    accepted = [item["t"] for item in accept_transitions(rows)]
    score = transition_f1(accepted, [5.0, 10.0], tolerance_s=manifest["transition_tolerance_s"])
    assert score >= manifest["transition_f1_min"], accepted


def test_continuous_scroll_is_not_a_cut():
    rows = activity_from_grays(scroll_frames(12))
    assert accept_transitions(rows) == []


def test_small_popup_is_suppressed():
    rows = [
        {"t": 1.0, "ssim_prev": 1.0, "bbox_area": 0.0, "cls": "static"},
        {"t": 2.0, "ssim_prev": 0.40, "bbox_area": 0.10, "cls": "content_change"},
        {"t": 3.0, "ssim_prev": 0.99, "bbox_area": 0.0, "cls": "static"},
        {"t": 4.0, "ssim_prev": 0.99, "bbox_area": 0.0, "cls": "static"},
    ]
    assert accept_transitions(rows) == []
