"""Alignment, signposts, dead air, silent demo, and the screen_flow document.

Spec §9.6–§9.7. E3-4. Numbers describe delivery. They do not say whether
anything on screen is true.
"""

from __future__ import annotations

from statistics import median, pstdev
from typing import Any, Optional

from pipeline.screen.textutil import (
    content_prefixes,
    content_tokens,
    phrase_hit_times,
    prefix,
    pronoun_tokens,
    tokenize,
)

DEAD_AIR_S = {"webinar": 4.0, "online_talk": 4.0, "recorded_video": 2.5}
STATIC_LONG_S = {"webinar": 120.0, "online_talk": 120.0, "recorded_video": 60.0}
SILENT_DEMO_S = 8.0
CLEAN_TOL_S = 0.7
PAUSE_MIN_S = 0.25
SIGNPOST_WINDOW_S = 5.0
RUSH_DWELL_S = 4.0
DEMO_WAIT_S = 5.0

METRIC_META = {
    "sf_narration_alignment_ratio": ("ratio", "research", "S61"),
    "sf_narration_lead_s_median": ("seconds", "heuristic", "H_S61"),
    "sf_clean_transition_ratio": ("ratio", "heuristic", "H"),
    "sf_signpost_ratio": ("ratio", "research", "S10"),
    "sf_dead_air_per_10min": ("per_10_min", "heuristic", "H"),
    "sf_silent_demo_ratio": ("ratio", "heuristic", "H"),
    "sf_static_long_ratio": ("ratio", "heuristic", "H_S60"),
    "sf_rushed_ratio": ("ratio", "heuristic", "H"),
    "sf_dwell_cv": ("ratio", "heuristic", "H"),
    "sf_demo_wait_events": ("count", "heuristic", "H"),
    "oe_interaction_prompts_per_10min": ("per_10_min", "heuristic", "H"),
    "oe_direct_address_per_100w": ("per_100w", "heuristic", "H"),
    "oe_open_speech_start_s": ("seconds", "research", "S74"),
    "oe_open_30s_dead_air_s": ("seconds", "research", "S74"),
    "oe_open_visual_change_s": ("seconds", "heuristic", "H"),
}


def _metric(
    metric_id: str,
    value: Optional[float],
    *,
    applicable: bool,
    confidence: float,
    failure_mode: Optional[str] = None,
) -> dict[str, Any]:
    unit, basis, source = METRIC_META[metric_id]
    return {
        "id": metric_id,
        "value": None if value is None else round(float(value), 4),
        "unit": unit,
        "confidence": round(float(confidence), 4),
        "applicable": bool(applicable and value is not None),
        "basis": basis,
        "source": source,
        "failure_mode": failure_mode,
    }


def _confidence(words: list[dict[str, Any]], dropped: int) -> float:
    if not words:
        base = 0.55
    else:
        base = sum(float(word.get("probability") or 0.0) for word in words) / len(words)
    penalty = min(0.2, dropped / 50.0)
    return max(0.4, min(0.95, base - penalty))


def _overlaps(start: float, end: float, spans: list[tuple[float, float]]) -> bool:
    return any(span_start < end and span_end > start for span_start, span_end in spans)


def _clip_spans(spans: list[tuple[float, float]], window: tuple[float, float]) -> list[tuple[float, float]]:
    w0, w1 = window
    clipped = []
    for start, end in spans:
        a = max(start, w0)
        b = min(end, w1)
        if b > a:
            clipped.append((a, b))
    return clipped


def _span_seconds(spans: list[tuple[float, float]]) -> float:
    return sum(end - start for start, end in spans)


def _quiet(t: float, activity_by_t: dict[int, dict[str, Any]], segments: list[dict[str, Any]], no_video: list[tuple[float, float]]) -> bool:
    if any(start <= t < end for start, end in no_video):
        return True
    for segment in segments:
        if segment["t_start"] <= t < segment["t_end"] and segment["type"] == "IDLE":
            return True
    row = activity_by_t.get(int(t))
    return bool(row and row.get("cls") == "static")


def _active_demo(t: float, activity_by_t: dict[int, dict[str, Any]], segments: list[dict[str, Any]]) -> bool:
    segment = next((item for item in segments if item["t_start"] <= t < item["t_end"]), None)
    if not segment or segment["type"] != "DEMO":
        return False
    row = activity_by_t.get(int(t))
    return bool(row and row.get("cls") in {"pointer", "scroll", "typing", "content_change"})


def _group_runs(seconds: list[int]) -> list[tuple[float, float]]:
    if not seconds:
        return []
    ordered = sorted(set(seconds))
    runs = []
    start = prev = ordered[0]
    for value in ordered[1:]:
        if value == prev + 1:
            prev = value
            continue
        runs.append((float(start), float(prev + 1)))
        start = prev = value
    runs.append((float(start), float(prev + 1)))
    return runs


def dead_air_events(
    *,
    activity: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    speech: list[tuple[float, float]],
    window: tuple[float, float],
    delivery_mode: str,
    no_video: Optional[list[tuple[float, float]]] = None,
) -> list[dict[str, Any]]:
    threshold = DEAD_AIR_S.get(delivery_mode, 4.0)
    w0, w1 = window
    by_t = {int(float(row["t"])): row for row in activity}
    quiet_seconds = []
    t = int(w0)
    while t < w1:
        second_start = float(t)
        second_end = second_start + 1.0
        if second_end <= w0 or second_start >= w1:
            t += 1
            continue
        speaking = _overlaps(second_start, second_end, speech)
        if not speaking and _quiet(second_start, by_t, segments, no_video or []):
            quiet_seconds.append(t)
        t += 1
    events = []
    for start, end in _group_runs(quiet_seconds):
        if end - start + 1e-6 >= threshold:
            events.append({"kind": "dead_air", "t": round(start, 3), "dur_s": round(end - start, 3)})
    return events


def silent_demo_events(
    *,
    activity: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    speech: list[tuple[float, float]],
    window: tuple[float, float],
) -> list[dict[str, Any]]:
    w0, w1 = window
    by_t = {int(float(row["t"])): row for row in activity}
    seconds = []
    t = int(w0)
    while t < w1:
        second_start = float(t)
        second_end = second_start + 1.0
        if not _overlaps(second_start, second_end, speech) and _active_demo(second_start, by_t, segments):
            seconds.append(t)
        t += 1
    events = []
    for start, end in _group_runs(seconds):
        if end - start + 1e-6 >= SILENT_DEMO_S:
            events.append({"kind": "silent_demo", "t": round(start, 3), "dur_s": round(end - start, 3)})
    return events


def _pause_distance(t: float, pauses: list[dict[str, Any]]) -> Optional[float]:
    best = None
    for pause in pauses:
        start = float(pause.get("start") or 0.0)
        end = float(pause.get("end") or start)
        if start <= t <= end:
            dist = 0.0
        elif t < start:
            dist = start - t
        else:
            dist = t - end
        if best is None or dist < best:
            best = dist
    return best


def _pause_near(t: float, pauses: list[dict[str, Any]]) -> bool:
    for pause in pauses:
        start = float(pause.get("start") or 0.0)
        end = float(pause.get("end") or start)
        if end - start < PAUSE_MIN_S:
            continue
        if start <= t <= end:
            dist = 0.0
        elif t < start:
            dist = start - t
        else:
            dist = t - end
        if dist <= CLEAN_TOL_S:
            return True
    return False


def _midword(t: float, words: list[dict[str, Any]]) -> bool:
    return any(float(word["start"]) < t < float(word["end"]) for word in words)


def _sentence_end_near(t: float, words: list[dict[str, Any]]) -> bool:
    for word in words:
        text = str(word.get("text") or "").rstrip()
        if text.endswith((".", "!", "?")) and abs(float(word["end"]) - t) <= CLEAN_TOL_S:
            return True
    return False


def _signpost_near(t: float, hits: list[tuple[float, str]]) -> bool:
    return any(abs(when - t) <= SIGNPOST_WINDOW_S for when, _phrase in hits)


def _first_mention(
    words: list[dict[str, Any]],
    screen_prefixes: set[str],
    onset: float,
    end: float,
    language: str,
) -> Optional[float]:
    seen: set[str] = set()
    for word in words:
        start = float(word["start"])
        if start < onset or start > end:
            continue
        for token in content_tokens(word.get("text") or "", language):
            key = prefix(token)
            if key in screen_prefixes:
                seen.add(key)
        if len(seen) >= 2:
            return start - onset
    return None


def _aligned(
    words: list[dict[str, Any]],
    screen_prefixes: set[str],
    onset: float,
    end: float,
    language: str,
) -> tuple[bool, list[str]]:
    shared: list[str] = []
    seen: set[str] = set()
    for word in words:
        start = float(word["start"])
        if start < onset - 2.0 or start > end:
            continue
        for token in content_tokens(word.get("text") or "", language):
            key = prefix(token)
            if key in screen_prefixes and key not in seen:
                seen.add(key)
                shared.append(token)
    return len(seen) >= 2, shared[:6]


def _question_hits(words: list[dict[str, Any]], language: str) -> list[tuple[float, Any]]:
    hits = []
    for word in words:
        if "?" not in str(word.get("text") or ""):
            continue
        window = [item for item in words if abs(float(item["start"]) - float(word["start"])) <= 4.0]
        if pronoun_tokens(window, language):
            hits.append((float(word["start"]), word.get("seg_id")))
    return hits


def _per_10(count: float, seconds: float) -> Optional[float]:
    if seconds <= 0:
        return None
    return count / (seconds / 600.0)


def build_screen_flow(
    *,
    delivery_mode: str,
    language: str,
    activity: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    words: list[dict[str, Any]],
    pauses: list[dict[str, Any]],
    speech: list[tuple[float, float]],
    window: tuple[float, float],
    screen_visible_s: float,
    lexicon: dict[str, Any],
    asr_dropped_words: int = 0,
    transition_engine: str = "ssim+pyscenedetect",
    ocr_engine: str = "tesseract",
    vad_source: str = "alignment",
    no_video: Optional[list[tuple[float, float]]] = None,
    camera_visible_s: Optional[float] = None,
    truncated: bool = False,
    vad_known: bool = True,
) -> dict[str, Any]:
    """View model for screen_flow.json. `content_judgment` is always false."""
    w0, w1 = window
    window_s = max(0.0, w1 - w0)
    confidence = _confidence(words, asr_dropped_words)
    signpost_phrases = list(lexicon.get("signposts") or [])
    interaction_phrases = list(lexicon.get("interaction_prompts") or [])
    demo_wait_phrases = list(lexicon.get("demo_waits") or [])
    signpost_hits = phrase_hit_times(words, signpost_phrases)
    interaction_hits = phrase_hit_times(words, interaction_phrases)
    question_hits = _question_hits(words, language)
    wait_hits = phrase_hit_times(words, demo_wait_phrases)

    if vad_known:
        dead = dead_air_events(
            activity=activity,
            segments=segments,
            speech=speech,
            window=window,
            delivery_mode=delivery_mode,
            no_video=no_video,
        )
        silent = silent_demo_events(activity=activity, segments=segments, speech=speech, window=window)
    else:
        dead = []
        silent = []

    by_t = {int(float(row["t"])): row for row in activity}
    demo_wait_count = 0
    for when, _phrase in wait_hits:
        following = [by_t[t] for t in range(int(when), int(when) + int(DEMO_WAIT_S)) if t in by_t]
        if len(following) >= int(DEMO_WAIT_S) and all(row.get("cls") == "static" for row in following):
            demo_wait_count += 1

    view_segments = []
    leads = []
    eligible = 0
    aligned_count = 0
    slide_dwells = []
    rushed = 0
    long_static_s = 0.0
    long_threshold = STATIC_LONG_S.get(delivery_mode, 120.0)
    clean_flags = []
    signpost_flags = []

    for segment in segments:
        onset = float(segment["t_start"])
        end = float(segment["t_end"])
        dwell = float(segment["dwell_s"])
        screen_keys = set(content_prefixes(segment.get("ocr_text") or "", language))
        word_count = int(segment.get("ocr_word_count") or len(content_tokens(segment.get("ocr_text") or "", language)))
        lead = None
        aligned = False
        shared: list[str] = []
        if len(content_tokens(segment.get("ocr_text") or "", language)) >= 4 or word_count >= 4:
            if segment["type"] in {"SLIDE", "DEMO"}:
                eligible += 1
                lead = _first_mention(words, screen_keys, onset, end, language)
                aligned, shared = _aligned(words, screen_keys, onset, end, language)
                if lead is not None:
                    leads.append(lead)
                if aligned:
                    aligned_count += 1
        transition_in = None
        if segment["index"] > 1:
            cut = next((item for item in transitions if abs(float(item["t"]) - onset) <= 0.51), None)
            cut_t = float(cut["t"]) if cut else onset
            clean = (not _midword(cut_t, words)) and (_pause_near(cut_t, pauses) or _sentence_end_near(cut_t, words))
            signpost = _signpost_near(cut_t, signpost_hits)
            nearest = _pause_distance(cut_t, pauses)
            transition_in = {
                "t": round(cut_t, 3),
                "clean": bool(clean),
                "nearest_pause_s": None if nearest is None else round(nearest, 3),
                "signpost": bool(signpost),
            }
            clean_flags.append(clean)
            signpost_flags.append(signpost)
        flags = []
        if any(event["t"] < end and event["t"] + event["dur_s"] > onset for event in silent):
            flags.append("silent_demo")
        if transition_in and not transition_in["clean"]:
            flags.append("talk_over_transition")
        if segment["type"] == "SLIDE":
            slide_dwells.append(dwell)
            if dwell < RUSH_DWELL_S:
                flags.append("rushed")
                rushed += 1
            pointer = float((segment.get("activity") or {}).get("pointer") or 0.0)
            if dwell > long_threshold and pointer <= 0.0:
                long_static_s += dwell
                flags.append("static_long")
        activity_view = {
            key: float((segment.get("activity") or {}).get(key) or 0.0)
            for key in ("static", "pointer", "scroll", "typing", "motion")
        }
        view_segments.append(
            {
                "id": f"scr_{int(segment['index']):03d}",
                "index": int(segment["index"]),
                "t_start": round(onset, 3),
                "t_end": round(end, 3),
                "dwell_s": round(dwell, 3),
                "type": segment["type"],
                "keyframe": segment.get("keyframe"),
                "ocr_word_count": word_count,
                "deck_page": segment.get("deck_page"),
                "activity": activity_view,
                "transition_in": transition_in,
                "narration": {
                    "first_mention_s": None if lead is None else round(lead, 3),
                    "shared_terms": shared,
                    "aligned": bool(aligned),
                },
                "flags": flags,
            }
        )

    demo_s = sum(float(segment["dwell_s"]) for segment in segments if segment["type"] == "DEMO")
    silent_s = sum(float(event["dur_s"]) for event in silent)
    slide_s = sum(slide_dwells)
    speech_in_window = _clip_spans(speech, window)
    speech_s = _span_seconds(speech_in_window)
    dead_rate = _per_10(len(dead), window_s)
    interaction_count = len(interaction_hits) + len(question_hits)
    interaction_rate = _per_10(interaction_count, speech_s) if speech_s > 0 else None
    tokens = []
    for word in words:
        if w0 <= float(word["start"]) <= w1:
            tokens.extend(tokenize(word.get("text") or ""))
    pronoun_count = len(pronoun_tokens([word for word in words if w0 <= float(word["start"]) <= w1], language))
    direct = (pronoun_count / len(tokens) * 100.0) if tokens else None

    if not vad_known:
        open_speech = None
        open_dead = None
    else:
        if speech_in_window:
            open_speech = max(0.0, speech_in_window[0][0] - w0)
        else:
            open_speech = window_s
        open_dead = 0.0
        for event in dead:
            overlap_start = max(float(event["t"]), w0)
            overlap_end = min(float(event["t"]) + float(event["dur_s"]), w0 + 30.0)
            if overlap_end > overlap_start:
                open_dead += overlap_end - overlap_start

    visual_change = None
    visual_applicable = delivery_mode == "recorded_video"
    if visual_applicable:
        marks = []
        if camera_visible_s is not None:
            marks.append(max(0.0, float(camera_visible_s) - w0))
        if transitions:
            marks.append(max(0.0, float(transitions[0]["t"]) - w0))
        visual_change = min(marks) if marks else window_s

    dwell_cv = None
    if len(slide_dwells) >= 2:
        mean = sum(slide_dwells) / len(slide_dwells)
        if mean > 0:
            dwell_cv = pstdev(slide_dwells) / mean
    elif len(slide_dwells) == 1:
        dwell_cv = 0.0

    events = []
    for event in dead + silent:
        events.append(event)
    for when, seg_id in interaction_hits:
        if w0 <= when <= w1:
            event = {"kind": "interaction_prompt", "t": round(when, 3), "dur_s": 0.0}
            if seg_id:
                event["text_ref"] = seg_id
            events.append(event)
    for when, seg_id in question_hits:
        if w0 <= when <= w1:
            events.append(
                {
                    "kind": "interaction_prompt",
                    "t": round(when, 3),
                    "dur_s": 0.0,
                    "text_ref": seg_id,
                }
            )
    for index, event in enumerate(events, start=1):
        event["id"] = f"ev_{index}"

    metrics = [
        _metric(
            "sf_narration_alignment_ratio",
            (aligned_count / eligible) if eligible else None,
            applicable=eligible > 0,
            confidence=confidence,
            failure_mode=None if eligible else "insufficient_screen_text",
        ),
        _metric(
            "sf_narration_lead_s_median",
            median(leads) if leads else None,
            applicable=bool(leads),
            confidence=confidence,
            failure_mode=None if leads else "no_first_mention",
        ),
        _metric(
            "sf_clean_transition_ratio",
            (sum(1 for flag in clean_flags if flag) / len(clean_flags)) if clean_flags else None,
            applicable=bool(clean_flags),
            confidence=confidence,
            failure_mode=None if clean_flags else "no_transitions",
        ),
        _metric(
            "sf_signpost_ratio",
            (sum(1 for flag in signpost_flags if flag) / len(signpost_flags)) if signpost_flags else None,
            applicable=bool(signpost_flags),
            confidence=confidence,
            failure_mode=None if signpost_flags else "no_transitions",
        ),
        _metric(
            "sf_dead_air_per_10min",
            dead_rate if vad_known else None,
            applicable=window_s > 0 and vad_known,
            confidence=confidence,
            failure_mode=None if (window_s > 0 and vad_known) else ("vad_missing" if not vad_known else "no_window"),
        ),
        _metric(
            "sf_silent_demo_ratio",
            (silent_s / demo_s) if demo_s > 0 and vad_known else None,
            applicable=demo_s > 0 and vad_known,
            confidence=confidence,
            failure_mode=None if (demo_s > 0 and vad_known) else ("vad_missing" if not vad_known else "no_demo"),
        ),
        _metric(
            "sf_static_long_ratio",
            (long_static_s / screen_visible_s) if screen_visible_s > 0 else None,
            applicable=screen_visible_s > 0 and slide_s > 0,
            confidence=confidence,
            failure_mode=None if slide_s > 0 else "no_slides",
        ),
        _metric(
            "sf_rushed_ratio",
            (rushed / len(slide_dwells)) if slide_dwells else None,
            applicable=bool(slide_dwells),
            confidence=confidence,
            failure_mode=None if slide_dwells else "no_slides",
        ),
        _metric(
            "sf_dwell_cv",
            dwell_cv,
            applicable=dwell_cv is not None,
            confidence=confidence,
            failure_mode=None if dwell_cv is not None else "no_slides",
        ),
        _metric(
            "sf_demo_wait_events",
            float(demo_wait_count),
            applicable=True,
            confidence=confidence,
        ),
        _metric(
            "oe_interaction_prompts_per_10min",
            interaction_rate,
            applicable=speech_s > 0,
            confidence=confidence,
            failure_mode=None if speech_s > 0 else "insufficient_speech",
        ),
        _metric(
            "oe_direct_address_per_100w",
            direct,
            applicable=bool(tokens),
            confidence=confidence,
            failure_mode=None if tokens else "insufficient_speech",
        ),
        _metric(
            "oe_open_speech_start_s",
            open_speech,
            applicable=window_s > 0 and vad_known,
            confidence=confidence,
            failure_mode=None if vad_known else "vad_missing",
        ),
        _metric(
            "oe_open_30s_dead_air_s",
            open_dead,
            applicable=window_s > 0 and vad_known,
            confidence=confidence,
            failure_mode=None if vad_known else "vad_missing",
        ),
        _metric(
            "oe_open_visual_change_s",
            visual_change,
            applicable=visual_applicable and visual_change is not None,
            confidence=confidence,
            failure_mode=None if visual_applicable else "not_recorded_video",
        ),
    ]
    return {
        "version": "1.0.0",
        "delivery_mode": delivery_mode,
        "screen_visible_s": round(float(screen_visible_s), 3),
        "segments": view_segments,
        "events": events,
        "metrics": metrics,
        "quality": {
            "asr_dropped_words": int(asr_dropped_words),
            "transition_engine": transition_engine,
            "ocr_engine": ocr_engine,
            "vad": vad_source,
            "truncated": bool(truncated),
        },
        "content_judgment": False,
    }
