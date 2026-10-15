"""Body tab and Slides tab view models (issue #48, SPEC §8.7).

Built from existing artifacts only. Missing inputs stay empty or N/A — values
are never invented. Expression series require expression_analysis. Suggested
assertion titles appear only when slides_v1 produced them, labeled AI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.slides.visual_aids import headline_type

BODY_EVENT_TYPES = (
    "self_adaptor",
    "crossed_arms",
    "clasped_fidget",
    "notes_down",
    "locomotion",
    "screen_turn",
)
SMILE_TYPES = ("smile", "flat_face")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _expression_granted(consents: dict[str, Any]) -> bool:
    purposes = consents.get("purposes") or {}
    return bool((purposes.get("expression_analysis") or {}).get("granted"))


def _metric_row(payload: dict[str, Any], metric_id: str) -> dict[str, Any] | None:
    row = (payload.get("metrics") or {}).get(metric_id)
    return row if isinstance(row, dict) else None


def _overlap_s(
    t0: float, t1: float, events: list[dict[str, Any]], kind: str
) -> float | None:
    found = False
    total = 0.0
    for event in events:
        if event.get("type") != kind:
            continue
        found = True
        a = float(event.get("t_start") or 0.0)
        b = float(event.get("t_end") or a)
        total += max(0.0, min(t1, b) - max(t0, a))
    return round(total, 3) if found else None


def build_body(output_dir: Path, duration_s: float | None = None) -> dict[str, Any]:
    dest = Path(output_dir)
    gesture = _read_json(dest / "gesture_metrics.json")
    gaze = _read_json(dest / "gaze_metrics.json")
    events_payload = _read_json(dest / "vision_events.json")
    quality = _read_json(dest / "vision_quality.json")
    expr = _read_json(dest / "expression_metrics.json")
    consents = _read_json(dest / "consents.json")
    events = list(events_payload.get("events") or [])
    duration = float(duration_s or 0.0)
    if duration <= 0 and gesture.get("activity_windows"):
        last = gesture["activity_windows"][-1]
        duration = float(last.get("start") or 0.0) + 1.0
    expr_on = _expression_granted(consents)
    heat = [
        {"t": round(float(w.get("start") or 0.0), 3), "value": w.get("value")}
        for w in (gesture.get("activity_windows") or [])
        if w.get("value") is not None
    ]
    event_rows = []
    for event in events:
        kind = str(event.get("type") or "")
        if kind in SMILE_TYPES and not expr_on:
            continue
        if kind not in BODY_EVENT_TYPES and kind not in SMILE_TYPES:
            continue
        event_rows.append(
            {
                "type": kind,
                "t_start": float(event.get("t_start") or 0.0),
                "t_end": float(event.get("t_end") or event.get("t_start") or 0.0),
            }
        )
    notes = [row for row in event_rows if row["type"] == "notes_down"]
    sway = _metric_row(gesture, "gb_sway_index")
    expressivity_points = []
    if expr_on:
        expressivity_points = [
            {"t": round(float(w.get("start") or 0.0), 3), "value": w.get("value")}
            for w in (expr.get("expressivity_windows") or [])
            if w.get("value") is not None
        ]
    available = bool(gesture or events or quality or gaze)
    return {
        "available": available,
        "duration_s": round(max(duration, 0.0), 3),
        "heat": heat,
        "space": gesture.get("space_density")
        or {"cols": 8, "rows": 6, "samples": 0, "cells": []},
        "events": event_rows,
        "sway": {
            "value": None if not sway else sway.get("value"),
            "unit": "shoulder_widths_sd",
            "applicable": bool(
                sway and sway.get("applicable") and sway.get("value") is not None
            ),
            "failure_mode": None if not sway else sway.get("failure_mode"),
        },
        "yaw_histogram": list(gaze.get("yaw_histogram") or []),
        "audience_facing_ratio": (
            _metric_row(gaze, "ec_audience_facing_ratio") or {}
        ).get("value"),
        "notes_down": notes,
        "expressivity": {
            "available": bool(expr_on and expressivity_points),
            "opt_in": True,
            "points": expressivity_points,
        },
        "quality": {
            "person_visible_ratio": quality.get("person_visible_ratio"),
            "face_visible_ratio": quality.get("face_visible_ratio"),
            "mean_face_height_px": quality.get("mean_face_height_px"),
            "mean_person_height_px": quality.get("mean_person_height_px"),
            "occlusion_ratio": quality.get("occlusion_ratio"),
            "camera_setup": quality.get("camera_setup") or {},
        }
        if quality
        else None,
        "emotion_inference": False,
    }


def build_slides_tab(output_dir: Path) -> dict[str, Any]:
    dest = Path(output_dir)
    slides_payload = _read_json(dest / "slides.json")
    glance = _read_json(dest / "slides_v1.json")
    events = list((_read_json(dest / "vision_events.json") or {}).get("events") or [])
    raw_slides = list(slides_payload.get("slides") or [])
    by_index = {
        int(g.get("index")): g
        for g in (glance.get("slides") or [])
        if g.get("index") is not None
    }
    items = []
    for slide in raw_slides:
        index = int(slide.get("index") or 0)
        g = by_index.get(index) or {}
        title = str(g.get("title") or slide.get("title") or "")
        title_type = g.get("title_type") or (headline_type(title) if title else None)
        t0 = slide.get("t_start")
        t1 = slide.get("t_end")
        facing = None
        if t0 is not None and t1 is not None:
            facing = _overlap_s(float(t0), float(t1), events, "screen_turn")
        suggested = g.get("suggested_assertion_title")
        has_kf = bool(slide.get("keyframe"))
        items.append(
            {
                "index": index,
                "t_start": t0,
                "t_end": t1,
                "dwell_s": slide.get("dwell_s"),
                "word_count": int(slide.get("word_count") or 0),
                "title": title,
                "title_type": title_type,
                "glance_level": g.get("glance_level"),
                "reading_overlap": slide.get("reading_overlap"),
                "facing_screen_s": facing,
                "has_keyframe": has_kf,
                "suggested_title": suggested
                if isinstance(suggested, str) and suggested.strip()
                else None,
                "suggestion_source": "ai" if suggested else None,
            }
        )
    return {
        "available": bool(items),
        "skip_reason": slides_payload.get("skip_reason"),
        "slides": items,
        "ai_suggestions": any(item.get("suggestion_source") == "ai" for item in items),
    }


def persist_body_slides(
    output_dir: Path, duration_s: float | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    dest = Path(output_dir)
    body = build_body(dest, duration_s=duration_s)
    slides = build_slides_tab(dest)
    (dest / "body.json").write_text(
        json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (dest / "slides_tab.json").write_text(
        json.dumps(slides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return body, slides


def keyframe_path(output_dir: Path, index: int) -> Path | None:
    slides = _read_json(Path(output_dir) / "slides.json")
    for slide in slides.get("slides") or []:
        if int(slide.get("index") or 0) != int(index):
            continue
        raw = slide.get("keyframe")
        if not raw:
            return None
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = Path(output_dir) / candidate
        return candidate if candidate.is_file() else None
    return None
