"""E3-4 scenarios 7–9, the ASR guard, and the 8 s silent-demo rule."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.screen.classify import classify_segments
from pipeline.screen.flow import build_screen_flow, dead_air_events, silent_demo_events
from pipeline.screen.textutil import drop_hallucinated_words

MANIFEST = Path(__file__).parent / "fixtures" / "screen_flow_manifest.json"
SCREEN = "network gateway policy review"
LEXICON = {
    "signposts": ["moving on", "next"],
    "interaction_prompts": ["in the chat"],
    "demo_waits": ["let it load"],
}


def _metric(document: dict, metric_id: str) -> dict:
    return next(item for item in document["metrics"] if item["id"] == metric_id)


def _speech_with_gaps(gaps, end):
    speech = []
    cursor = 0.0
    for start, stop in gaps:
        if start > cursor:
            speech.append((cursor, start))
        cursor = stop
    if cursor < end:
        speech.append((cursor, end))
    return speech


def _activity(length, scroll_start, scroll_end):
    rows = []
    for t in range(length):
        if scroll_start <= t < scroll_end:
            rows.append({"t": float(t), "cls": "scroll", "changed_ratio": 0.2, "bbox_area": 0.8, "ssim_prev": 0.7})
        else:
            rows.append({"t": float(t), "cls": "static", "changed_ratio": 0.0, "bbox_area": 0.0, "ssim_prev": 1.0})
    return rows


def test_scenario_7_dead_air_and_silent_demo():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["scenarios"]["7"]
    window = float(manifest["window_s"])
    activity = _activity(int(window), 200, 260)
    segments = classify_segments(
        activity,
        [200.0, 260.0],
        window,
        ocr_for=lambda _start, _end: (SCREEN, 4, None),
    )
    gaps = [(20.0, 26.0), (50.0, 56.0), (90.0, 96.0), (220.0, 228.0)]
    speech = _speech_with_gaps(gaps, window)
    document = build_screen_flow(
        delivery_mode="webinar",
        language="en",
        activity=activity,
        transitions=[{"t": 200.0, "ssim": 0.4}, {"t": 260.0, "ssim": 0.4}],
        segments=segments,
        words=[],
        pauses=[],
        speech=speech,
        window=(0.0, window),
        screen_visible_s=window,
        lexicon=LEXICON,
    )
    dead = [event for event in document["events"] if event["kind"] == "dead_air"]
    assert len(dead) == manifest["dead_air_count"]
    assert _metric(document, "sf_dead_air_per_10min")["value"] == 3.0
    silent = _metric(document, "sf_silent_demo_ratio")
    assert silent["applicable"] is True
    assert silent["value"] > 0
    assert document["content_judgment"] is False


def test_six_second_scroll_gap_is_not_a_silent_demo():
    activity = _activity(30, 0, 30)
    segments = [{"index": 1, "t_start": 0.0, "t_end": 30.0, "dwell_s": 30.0, "type": "DEMO", "ocr_text": "", "ocr_word_count": 0, "activity": {"scroll": 1}}]
    short = silent_demo_events(activity=activity[:6], segments=segments, speech=[], window=(0.0, 6.0))
    assert short == []
    long = silent_demo_events(activity=activity[:8], segments=segments, speech=[], window=(0.0, 8.0))
    assert len(long) == 1


def test_recorded_video_dead_air_is_shorter_than_webinar():
    activity = _activity(10, 0, 0)
    segments = [{"index": 1, "t_start": 0.0, "t_end": 10.0, "dwell_s": 10.0, "type": "SLIDE", "ocr_text": SCREEN, "ocr_word_count": 4, "activity": {"static": 1}}]
    speech = [(0.0, 1.0), (4.0, 10.0)]
    webinar = dead_air_events(activity=activity, segments=segments, speech=speech, window=(0.0, 10.0), delivery_mode="webinar")
    recorded = dead_air_events(activity=activity, segments=segments, speech=speech, window=(0.0, 10.0), delivery_mode="recorded_video")
    assert webinar == []
    assert len(recorded) == 1


def test_scenario_8_clean_transition_ratio():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["scenarios"]["8"]
    cuts = [float(t) for t in range(10, 101, 10)]
    segments = []
    for index, start in enumerate([0.0, *cuts]):
        end = cuts[index] if index < len(cuts) else 110.0
        segments.append(
            {
                "index": index + 1,
                "t_start": start,
                "t_end": end,
                "dwell_s": end - start,
                "type": "SLIDE",
                "ocr_text": SCREEN,
                "ocr_word_count": 4,
                "deck_page": None,
                "activity": {"static": 1.0, "pointer": 0.0},
            }
        )
    words = []
    for cut in cuts[:4]:
        words.append({"text": "network", "start": cut - 0.4, "end": cut + 0.4, "probability": 0.9, "seg_id": "s1"})
    pauses = [{"start": cut - 0.2, "end": cut + 0.2, "duration": 0.4} for cut in cuts[4:]]
    document = build_screen_flow(
        delivery_mode="webinar",
        language="en",
        activity=[],
        transitions=[{"t": cut} for cut in cuts],
        segments=segments,
        words=words,
        pauses=pauses,
        speech=[(0.0, 110.0)],
        window=(0.0, 110.0),
        screen_visible_s=110.0,
        lexicon=LEXICON,
    )
    ratio = _metric(document, "sf_clean_transition_ratio")["value"]
    assert abs(ratio - manifest["clean_ratio"]) <= manifest["tolerance"]


def test_scenario_9_alignment_and_lead():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["scenarios"]["9"]
    segments = []
    words = []
    for index in range(10):
        start = index * 10.0
        segments.append(
            {
                "index": index + 1,
                "t_start": start,
                "t_end": start + 10.0,
                "dwell_s": 10.0,
                "type": "SLIDE",
                "ocr_text": SCREEN,
                "ocr_word_count": 4,
                "deck_page": None,
                "activity": {"static": 1.0, "pointer": 0.0},
            }
        )
        if index < 8:
            words.append({"text": "network", "start": start + 3.0, "end": start + 3.4, "probability": 0.95, "seg_id": f"s{index}"})
            words.append({"text": "gateway", "start": start + 3.0, "end": start + 3.5, "probability": 0.95, "seg_id": f"s{index}"})
        else:
            words.append({"text": "unrelated", "start": start + 3.0, "end": start + 3.4, "probability": 0.95, "seg_id": f"s{index}"})
            words.append({"text": "filler", "start": start + 3.5, "end": start + 3.8, "probability": 0.95, "seg_id": f"s{index}"})
    document = build_screen_flow(
        delivery_mode="online_talk",
        language="en",
        activity=[],
        transitions=[],
        segments=segments,
        words=words,
        pauses=[],
        speech=[(0.0, 100.0)],
        window=(0.0, 100.0),
        screen_visible_s=100.0,
        lexicon=LEXICON,
    )
    aligned = _metric(document, "sf_narration_alignment_ratio")["value"]
    lead = _metric(document, "sf_narration_lead_s_median")["value"]
    assert aligned >= manifest["alignment_min"]
    assert abs(lead - manifest["lead_s"]) <= manifest["lead_tolerance_s"]
    assert document["content_judgment"] is False


def test_asr_guard_drops_low_probability_words_in_silence():
    words = [
        {"text": "network", "start": 1.2, "end": 1.6, "probability": 0.2, "seg_id": "h"},
        {"text": "gateway", "start": 1.6, "end": 2.0, "probability": 0.9, "seg_id": "h"},
        {"text": "policy", "start": 5.0, "end": 5.4, "probability": 0.2, "seg_id": "k"},
    ]
    speech = [(4.0, 8.0)]
    kept, dropped = drop_hallucinated_words(words, speech, 8.0)
    assert dropped == 1
    assert all(word["text"] != "network" for word in kept)
    assert any(word["text"] == "policy" for word in kept)
    segments = [
        {
            "index": 1,
            "t_start": 0.0,
            "t_end": 8.0,
            "dwell_s": 8.0,
            "type": "SLIDE",
            "ocr_text": SCREEN,
            "ocr_word_count": 4,
            "activity": {"static": 1.0, "pointer": 0.0},
        }
    ]
    document = build_screen_flow(
        delivery_mode="webinar",
        language="en",
        activity=_activity(8, 0, 0),
        transitions=[],
        segments=segments,
        words=kept,
        pauses=[],
        speech=speech,
        window=(0.0, 8.0),
        screen_visible_s=8.0,
        lexicon=LEXICON,
        asr_dropped_words=dropped,
    )
    assert document["quality"]["asr_dropped_words"] == 1
    narration = document["segments"][0]["narration"]
    assert "network" not in narration["shared_terms"]


def test_signpost_near_a_cut():
    segments = [
        {
            "index": 1,
            "t_start": 0.0,
            "t_end": 10.0,
            "dwell_s": 10.0,
            "type": "SLIDE",
            "ocr_text": SCREEN,
            "ocr_word_count": 4,
            "activity": {"static": 1.0, "pointer": 0.0},
        },
        {
            "index": 2,
            "t_start": 10.0,
            "t_end": 20.0,
            "dwell_s": 10.0,
            "type": "SLIDE",
            "ocr_text": SCREEN,
            "ocr_word_count": 4,
            "activity": {"static": 1.0, "pointer": 0.0},
        },
    ]
    words = [
        {"text": "moving", "start": 9.0, "end": 9.3, "probability": 0.9, "seg_id": "s"},
        {"text": "on", "start": 9.3, "end": 9.5, "probability": 0.9, "seg_id": "s"},
    ]
    document = build_screen_flow(
        delivery_mode="webinar",
        language="en",
        activity=[],
        transitions=[{"t": 10.0}],
        segments=segments,
        words=words,
        pauses=[{"start": 9.6, "end": 10.2, "duration": 0.6}],
        speech=[(0.0, 20.0)],
        window=(0.0, 20.0),
        screen_visible_s=20.0,
        lexicon=LEXICON,
    )
    assert document["segments"][1]["transition_in"]["signpost"] is True
