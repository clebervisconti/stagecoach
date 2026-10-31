"""SLIDE / DEMO / VIDEO / IDLE from layout and behaviour only (spec §9.5.3, E3-3).

The cut second itself is not part of the segment mix. A laser pointer on a
slide stays SLIDE. Scroll, typing, or a burst of content changes is DEMO.
"""

from __future__ import annotations

from typing import Any, Optional

SLIDE_STATIC_POINTER = 0.80
DEMO_ACTIVE = 0.25
VIDEO_MOTION = 0.60
VIDEO_RATIO = 0.15
VIDEO_RUN_S = 5
IDLE_STATIC = 0.90
IDLE_WORDS = 3
CONTENT_BURST = 3
CONTENT_WINDOW_S = 30.0
ACTIVE = frozenset({"pointer", "scroll", "typing"})
DEMO_STRONG = frozenset({"scroll", "typing"})


def segment_bounds(transition_times: list[float], duration_s: float) -> list[tuple[float, float]]:
    if duration_s <= 0:
        return []
    cuts = sorted({round(float(t), 3) for t in transition_times if 0.25 < float(t) < duration_s - 0.25})
    points = [0.0, *cuts, float(duration_s)]
    bounds = []
    for start, end in zip(points, points[1:]):
        if end - start >= 0.5:
            bounds.append((float(start), float(end)))
    return bounds or [(0.0, float(duration_s))]


def _samples(
    activity: list[dict[str, Any]],
    start: float,
    end: float,
    cuts: list[float],
) -> list[dict[str, Any]]:
    inside = [row for row in activity if start <= float(row["t"]) < end]
    quiet = [
        row
        for row in inside
        if not any(abs(float(row["t"]) - cut) <= 0.51 for cut in cuts)
    ]
    return quiet or inside


def _share(rows: list[dict[str, Any]], classes: frozenset[str] | set[str]) -> float:
    if not rows:
        return 0.0
    hit = sum(1 for row in rows if row.get("cls") in classes)
    return hit / len(rows)


def _longest_run(rows: list[dict[str, Any]], predicate) -> int:
    best = 0
    current = 0
    for row in rows:
        if predicate(row):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _content_burst(rows: list[dict[str, Any]]) -> bool:
    times = [float(row["t"]) for row in rows if row.get("cls") == "content_change"]
    if len(times) < CONTENT_BURST:
        return False
    for start in times:
        window = [t for t in times if start <= t <= start + CONTENT_WINDOW_S]
        if len(window) >= CONTENT_BURST:
            return True
    return False


def _shares(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = ("static", "pointer", "scroll", "typing", "motion", "content_change")
    if not rows:
        return {key: 0.0 for key in keys}
    total = float(len(rows))
    return {key: round(sum(1 for row in rows if row.get("cls") == key) / total, 4) for key in keys}


def classify_segment(
    rows: list[dict[str, Any]],
    *,
    ocr_word_count: int = 0,
    deck_page: Optional[int] = None,
) -> str:
    """One segment. Behaviour and word count only. Never whether the words are correct."""
    has_text = int(ocr_word_count) >= IDLE_WORDS or deck_page is not None
    static_pointer = _share(rows, frozenset({"static", "pointer"}))
    strong = _share(rows, DEMO_STRONG)
    active = _share(rows, ACTIVE)
    motion = _share(rows, frozenset({"motion"}))
    motion_run = _longest_run(
        rows,
        lambda row: row.get("cls") == "motion" and float(row.get("changed_ratio") or 0.0) >= VIDEO_RATIO,
    )
    if motion >= VIDEO_MOTION and motion_run >= VIDEO_RUN_S:
        return "VIDEO"
    if strong >= DEMO_ACTIVE or _content_burst(rows):
        return "DEMO"
    if static_pointer >= SLIDE_STATIC_POINTER and has_text:
        return "SLIDE"
    if active >= DEMO_ACTIVE:
        return "DEMO"
    if _share(rows, frozenset({"static"})) >= IDLE_STATIC and not has_text:
        return "IDLE"
    if has_text:
        return "SLIDE"
    if motion >= VIDEO_MOTION:
        return "VIDEO"
    return "IDLE"


def classify_segments(
    activity: list[dict[str, Any]],
    transition_times: list[float],
    duration_s: float,
    *,
    ocr_for=None,
) -> list[dict[str, Any]]:
    """`ocr_for(t_start, t_end) -> (text, word_count, deck_page)` or None."""
    bounds = segment_bounds(transition_times, duration_s)
    segments = []
    for index, (start, end) in enumerate(bounds, start=1):
        rows = _samples(activity, start, end, transition_times)
        text = ""
        word_count = 0
        deck_page = None
        if ocr_for is not None:
            found = ocr_for(start, end) or ("", 0, None)
            text = str(found[0] or "")
            word_count = int(found[1] if found[1] is not None else len(text.split()))
            deck_page = found[2]
        kind = classify_segment(rows, ocr_word_count=word_count, deck_page=deck_page)
        segments.append(
            {
                "index": index,
                "t_start": round(start, 3),
                "t_end": round(end, 3),
                "dwell_s": round(end - start, 3),
                "type": kind,
                "ocr_text": text,
                "ocr_word_count": word_count,
                "deck_page": deck_page,
                "activity": _shares(rows),
                "samples": rows,
            }
        )
    return segments
