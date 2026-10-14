"""Category 8 visual-aids metrics from slides.json (issue #44, SPEC §4.4.8).

Ids match scoring.yaml v1.0.0. Missing inputs stay N/A, never a made-up score.
"""

from __future__ import annotations

from statistics import median
from typing import Any, Optional

from pipeline.slides.match import reading_overlap, tokenize

UNITS = {
    "va_words_per_slide_median": "words",
    "va_dense_slide_ratio": "ratio",
    "va_assertion_headline_ratio": "ratio",
    "va_reading_ratio": "ratio",
    "va_screen_facing_s_per_min": "s_per_min",
    "va_glance_llm": "llm_level",
}

DENSE_WORDS = 40
READING_FLAG = 0.6
DECK_ONLY_CONF = 0.6
ASSERT_VERBS = {
    "is", "are", "was", "were", "will", "must", "should", "need", "needs",
    "shipped", "grew", "cut", "raise", "stop", "start", "make", "makes",
    "can't", "cannot", "don't", "does", "do", "has", "have",
}


def _metric(metric_id: str, value: Optional[float], *, applicable: bool, confidence: float, failure_mode: Optional[str] = None) -> dict[str, Any]:
    return {
        "id": metric_id,
        "value": None if value is None else round(float(value), 4),
        "unit": UNITS[metric_id],
        "basis": "llm_judgment" if metric_id == "va_glance_llm" else "heuristic",
        "source": "S3" if metric_id == "va_glance_llm" else ("S11" if metric_id == "va_assertion_headline_ratio" else "H"),
        "confidence": round(float(confidence), 4),
        "applicable": bool(applicable and value is not None),
        "failure_mode": failure_mode,
    }


def _is_data_slide(text: str, word_count: int) -> bool:
    tokens = tokenize(text)
    if not tokens:
        return False
    digits = sum(1 for t in tokens if any(ch.isdigit() for ch in t))
    return word_count <= 12 and digits / max(len(tokens), 1) >= 0.4


def headline_type(title: str) -> str:
    """Heuristic title class when slides_v1 is absent: assertion / topic / none (H)."""
    words = tokenize(title)
    if not words:
        return "none"
    if len(words) >= 5 and (any(w in ASSERT_VERBS for w in words) or title.strip().endswith(".")):
        return "assertion"
    if len(words) >= 6:
        return "assertion"
    return "topic"


def _align_deck_only(slides: list[dict[str, Any]], transcript: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign transcript windows by order when dwell times are missing (H)."""
    segs = list((transcript or {}).get("segments") or [])
    if not slides or not segs:
        return slides
    t0 = float(segs[0].get("start") or 0.0)
    t1 = float(segs[-1].get("end") or segs[-1].get("start") or 0.0)
    span = max(t1 - t0, 0.1)
    n = len(slides)
    out = []
    for i, slide in enumerate(slides):
        start = t0 + span * i / n
        end = t0 + span * (i + 1) / n
        spoken = " ".join(
            str(s.get("text") or "")
            for s in segs
            if float(s.get("end") or 0) >= start and float(s.get("start") or 0) <= end
        )
        row = dict(slide)
        row["t_start"] = start
        row["t_end"] = end
        row["dwell_s"] = end - start
        if row.get("reading_overlap") is None:
            row["reading_overlap"] = reading_overlap(str(row.get("text") or ""), spoken)
        out.append(row)
    return out


def screen_facing_s_per_min(events: list[dict[str, Any]], duration_s: float) -> Optional[float]:
    if duration_s <= 0:
        return None
    total = 0.0
    found = False
    for event in events:
        if event.get("type") != "screen_turn":
            continue
        found = True
        total += max(0.0, float(event.get("t_end") or 0) - float(event.get("t_start") or 0))
    if not found:
        return None
    return total * (60.0 / duration_s)


def compute_visual_aids_metrics(
    slides_payload: Optional[dict[str, Any]],
    *,
    transcript: Optional[dict[str, Any]] = None,
    vision_events: Optional[list[dict[str, Any]]] = None,
    duration_s: float = 1.0,
    glance: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Return va_* rows or None when there is no deck and no detected slides."""
    slides = list((slides_payload or {}).get("slides") or [])
    if not slides:
        return None
    deck_only = all(s.get("t_start") is None for s in slides)
    if deck_only:
        slides = _align_deck_only(slides, transcript)
    conf = DECK_ONLY_CONF if deck_only else 0.75

    content_counts = []
    for slide in slides:
        wc = int(slide.get("word_count") or 0)
        text = str(slide.get("text") or "")
        title = str(slide.get("title") or "")
        body_words = wc - len(tokenize(title))
        if _is_data_slide(text, wc):
            continue
        content_counts.append(max(body_words, 0) if body_words > 0 else wc)

    words_median = float(median(content_counts)) if content_counts else None
    dense = sum(1 for s in slides if int(s.get("word_count") or 0) > DENSE_WORDS) / len(slides)

    types = []
    glance_levels = []
    per_slide = (glance or {}).get("slides") or []
    by_index = {int(g.get("index")): g for g in per_slide if g.get("index") is not None}
    for slide in slides:
        g = by_index.get(int(slide.get("index") or 0))
        title = str((g or {}).get("title") or slide.get("title") or "")
        ttype = (g or {}).get("title_type") or headline_type(title)
        types.append(ttype)
        if g and g.get("glance_level") is not None:
            glance_levels.append(float(g["glance_level"]))

    assertion_ratio = types.count("assertion") / len(types) if types else None

    dwells = [float(s["dwell_s"]) for s in slides if s.get("dwell_s")]
    flagged = 0.0
    dwell_total = sum(dwells) if dwells else 0.0
    if dwell_total > 0:
        for slide in slides:
            d = float(slide.get("dwell_s") or 0)
            ov = slide.get("reading_overlap")
            if ov is None:
                ov = reading_overlap(str(slide.get("text") or ""), "")
            if ov is not None and ov > READING_FLAG:
                flagged += d
        reading_ratio = flagged / dwell_total
    else:
        reading_ratio = None

    reading_conf = conf * DECK_ONLY_CONF if deck_only else conf
    facing = screen_facing_s_per_min(vision_events or [], duration_s)
    glance_level = median(glance_levels) if glance_levels else None

    metrics = {
        "va_words_per_slide_median": _metric(
            "va_words_per_slide_median", words_median, applicable=words_median is not None, confidence=conf
        ),
        "va_dense_slide_ratio": _metric("va_dense_slide_ratio", dense, applicable=True, confidence=conf),
        "va_assertion_headline_ratio": _metric(
            "va_assertion_headline_ratio",
            assertion_ratio,
            applicable=assertion_ratio is not None,
            confidence=conf * (0.7 if not glance else 1.0),
        ),
        "va_reading_ratio": _metric(
            "va_reading_ratio",
            reading_ratio,
            applicable=reading_ratio is not None,
            confidence=reading_conf,
            failure_mode="deck_only_aligned" if deck_only else None,
        ),
        "va_screen_facing_s_per_min": _metric(
            "va_screen_facing_s_per_min",
            facing,
            applicable=facing is not None and not deck_only,
            confidence=conf,
            failure_mode=None if facing is not None else "no_screen_turn_events",
        ),
        "va_glance_llm": _metric(
            "va_glance_llm",
            glance_level,
            applicable=glance_level is not None,
            confidence=0.7 if glance_level is not None else 0.0,
            failure_mode=None if glance_level is not None else "slides_v1_unavailable",
        ),
    }
    return {
        "deck_only": deck_only,
        "slide_count": len(slides),
        "glance_used": bool(glance_levels),
        "metrics": metrics,
    }
