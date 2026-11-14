"""Practice loop, quotas, online signals, and stage-parity of config 1.1.0."""

from datetime import date

from scoring.practice import (
    baseline_sentence,
    deck_review,
    evaluate_quota,
    list_drills,
    online_report,
    propose_layout,
    region_from_normalized,
    score_answer,
    score_text_drill,
    series_compare,
    transcript_signals,
    weekly_plan,
)


def test_text_drills_and_answer_first():
    claim = score_text_drill("bluf_rewrite", "Ship the claim before the background story")
    assert claim["applicable"] is True
    assert claim["score"] >= 80
    long = score_text_drill("bluf_rewrite", " ".join(["word"] * 40))
    assert long["score"] < claim["score"]
    answer = score_answer("Yes, we should cut the demo. It hides the ask.")
    assert answer["score"] >= 80
    throat = score_answer("That's a great question. We can discuss the roadmap later today.")
    assert throat["metrics"]["throat_clearing"] is True
    assert throat["score"] < answer["score"]


def test_weekly_plan_uses_weakest_applicable_category():
    plan = weekly_plan(
        categories=[
            {"category_id": "fluency", "score": 40, "applicable": True},
            {"category_id": "visual_aids", "score": 90, "applicable": True},
            {"category_id": "qa", "score": None, "applicable": False},
        ],
        goals=[
            {
                "id": "g1",
                "metric_id": "pp_wpm",
                "target": 140,
                "comparator": "<=",
                "achieved_at": None,
            }
        ],
        talk_date=date(2026, 11, 20),
        today=date(2026, 11, 12),
        locale="en",
    )
    drills = [item for item in plan["items"] if item["kind"] == "drill"]
    assert drills[0]["category_id"] == "fluency"
    assert plan["items"][0]["kind"] == "talk_date"
    assert any(item["kind"] == "goal" for item in plan["items"])


def test_series_requires_two_comparable_takes():
    empty = series_compare(
        [{"session_id": "a", "language": "en", "config_version": "1.0.0", "overall": 50}]
    )
    assert empty["ready"] is False
    body = series_compare(
        [
            {
                "session_id": "a",
                "language": "en",
                "config_version": "1.0.0",
                "overall": 50,
                "categories": {"fluency": 40},
            },
            {
                "session_id": "b",
                "language": "en",
                "config_version": "1.1.0",
                "overall": 62,
                "categories": {"fluency": 55},
            },
        ]
    )
    assert body["ready"] is True
    assert body["overall_delta"] == 12
    assert body["deltas"]["fluency"] == 15


def test_transcript_and_deck_do_not_replace_the_session_score():
    signals = transcript_signals(
        "This is a short sentence. This sentence runs on and on with many extra words "
        "that push it well past the long sentence line."
    )
    assert signals["applicable"] is True
    assert "original analysis" in signals["note"]
    review = deck_review([{"text": "Ship the weekly digest to managers"}, {"text": "Overview"}])
    assert review["applicable"] is True
    assert "true" in review["note"]


def test_layout_and_online_signals_leave_stage_unchanged():
    stage = propose_layout("stage", "stage")
    assert stage["kind"] == "stage_wide"
    assert stage["needs_review"] is False
    online = propose_layout("webinar", "screen_recording")
    roles = {region["role"] for region in online["segments"][0]["regions"]}
    assert "camera" in roles and "screen" in roles
    assert "other_participant" not in roles
    stage_report = online_report(delivery_mode="stage", layout=stage)
    assert all(row["score"] is None for row in stage_report["signals"].values())
    measured = online_report(
        delivery_mode="webinar",
        layout=online,
        duration_s=600,
        slide_count=8,
        dead_air_s=10,
        qa_in_slot=True,
    )
    assert measured["signals"]["screen_flow"]["applicable"] is True
    assert measured["population_overall"] is None
    box = region_from_normalized({"x": 0.5, "y": 0.5, "w": 0.5, "h": 0.5}, 100, 80)
    assert box["w"] == 50 and box["h"] == 40


def test_quota_blocks_a_second_job_and_a_full_month():
    blocked = evaluate_quota(
        storage_bytes=0,
        incoming_bytes=10,
        active_jobs=1,
        monthly_seconds=0,
        reserved_seconds=60,
        storage_limit=1000,
        active_limit=1,
        monthly_limit=600,
    )
    assert blocked["allowed"] is False
    full = evaluate_quota(
        storage_bytes=0,
        incoming_bytes=10,
        active_jobs=0,
        monthly_seconds=500,
        reserved_seconds=200,
        storage_limit=1000,
        active_limit=1,
        monthly_limit=600,
    )
    assert "minutes" in full["reason"]
    ok = evaluate_quota(
        storage_bytes=10,
        incoming_bytes=10,
        active_jobs=0,
        monthly_seconds=10,
        reserved_seconds=60,
        storage_limit=1000,
        active_limit=1,
        monthly_limit=600,
    )
    assert ok["allowed"] is True


def test_baseline_sentence_and_drill_catalog_locales():
    sentence = baseline_sentence(4.0, 6.0)
    assert sentence is not None
    assert "population score" in sentence
    en = list_drills("en")
    pt = list_drills("pt-BR")
    assert len(en) >= 10
    assert en[0]["title"] != pt[0]["title"]
    drills = __import__("scoring.practice", fromlist=["DRILLS"]).DRILLS
    joined = " ".join(
        drill["instructions"]["en"] + drill["instructions"]["pt-BR"] for drill in drills
    )
    for banned in ("nervous", "anxious", "engagement", "authenticity", "nervoso", "engajamento"):
        assert banned not in joined.lower()
