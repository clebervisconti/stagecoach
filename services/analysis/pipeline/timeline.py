"""Video-synced timeline lanes (issue #47, SPEC §8.4).

Lanes are built from existing artifacts only. Missing inputs leave a lane empty
or unavailable — spans are never invented. Smiles stay off without
expression_analysis events.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SPRITE_INTERVAL_S = 5
RUSHING_WPM = 165.0  # keynote band high (H, SPEC §4.4.9)
MONOTONE_PVQ = 0.08
ACTIVITY_ON = 0.15
LANE_IDS = (
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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _item(t_start: float, t_end: float, label: str, kind: str = "") -> dict[str, Any]:
    start = max(0.0, float(t_start))
    end = max(start, float(t_end))
    return {
        "t_start": round(start, 3),
        "t_end": round(end, 3),
        "label": label,
        "kind": kind or label,
    }


def _seg_lookup(transcript: dict[str, Any]) -> dict[str, tuple[float, float]]:
    out: dict[str, tuple[float, float]] = {}
    segs = transcript.get("segments") or []
    for i, seg in enumerate(segs):
        start = float(seg.get("start") or 0.0)
        end = float(seg.get("end") or start)
        sid = seg.get("id")
        keys = {str(i), f"S{i:04d}", f"S{i + 1:04d}"}
        if sid is not None:
            keys.add(str(sid))
            if isinstance(sid, int):
                keys.add(f"S{sid:04d}")
                keys.add(f"S{sid + 1:04d}")
        for key in keys:
            out.setdefault(key, (start, end))
    return out


def _span_for_seg(
    lookup: dict[str, tuple[float, float]], start_seg: Any, end_seg: Any
) -> tuple[float, float] | None:
    a = lookup.get(str(start_seg))
    b = lookup.get(str(end_seg), a)
    if not a:
        return None
    return a[0], (b or a)[1]


def _lane(
    lane_id: str,
    items: list[dict[str, Any]],
    *,
    available: bool = True,
    opt_in: bool = False,
) -> dict[str, Any]:
    return {
        "id": lane_id,
        "available": available,
        "opt_in": opt_in,
        "default_on": available and lane_id != "smiles",
        "items": items,
    }


def _sections(
    content: dict[str, Any], lookup: dict[str, tuple[float, float]]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in (content.get("outline") or {}).get("sections") or []:
        span = _span_for_seg(lookup, row.get("start_seg"), row.get("end_seg"))
        if not span:
            continue
        items.append(
            _item(span[0], span[1], str(row.get("title") or "Section"), "section")
        )
    return items


def _slides(slides: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in slides.get("slides") or []:
        start = row.get("t_start")
        end = row.get("t_end")
        if start is None or end is None:
            continue
        label = str(row.get("title") or f"Slide {row.get('index', len(items) + 1)}")
        items.append(_item(float(start), float(end), label, "slide"))
    return items


def _fillers(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for seg in transcript.get("segments") or []:
        for word in seg.get("words") or []:
            tags = {str(t) for t in (word.get("tags") or [])}
            token = str(word.get("word") or word.get("w") or "")
            if "filler_sound" in tags or "filler_word" in tags:
                start = float(word.get("start") or 0.0)
                end = float(word.get("end") or start)
                items.append(_item(start, end, token or "filler", "filler"))
    return items


def _long_pauses(pauses: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for pause in pauses.get("pauses") or []:
        kind = str(pause.get("kind") or "")
        duration = float(pause.get("duration") or 0.0)
        if kind != "long" and duration < 3.0:
            continue
        start = float(pause.get("start") or 0.0)
        end = float(pause.get("end") or start + duration)
        items.append(_item(start, end, f"Pause {duration:.1f}s", "long_pause"))
    return items


def _rushing(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[tuple[float, float]] = []
    for seg in transcript.get("segments") or []:
        for word in seg.get("words") or []:
            token = str(word.get("word") or word.get("w") or "").strip()
            tags = {str(t) for t in (word.get("tags") or [])}
            if not token or "filler_sound" in tags:
                continue
            words.append(
                (float(word.get("start") or 0.0), float(word.get("end") or 0.0))
            )
        if not seg.get("words"):
            tokens = str(seg.get("text") or "").split()
            start = float(seg.get("start") or 0.0)
            end = float(seg.get("end") or start)
            step = (end - start) / max(len(tokens), 1)
            for i, token in enumerate(tokens):
                if token:
                    words.append((start + i * step, start + (i + 1) * step))
    if not words:
        return []
    t0 = min(w[0] for w in words)
    t1 = max(w[1] for w in words)
    items: list[dict[str, Any]] = []
    t = t0
    window = 30.0
    while t + window <= t1 + 1e-9:
        count = sum(1 for w in words if t <= w[0] < t + window)
        wpm = count / (window / 60.0)
        if wpm > RUSHING_WPM:
            items.append(_item(t, t + window, f"{int(wpm)} WPM", "rushing"))
        t += 10.0
    return items


def _monotone(audio: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in audio.get("pvq_windows") or []:
        value = row.get("value")
        if value is None or float(value) >= MONOTONE_PVQ:
            continue
        start = float(row.get("start") or 0.0)
        end = float(row.get("end") or start + 10.0)
        items.append(_item(start, end, "Monotone window", "monotone"))
    return items


def _gestures(gesture: dict[str, Any], events: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in gesture.get("activity_windows") or []:
        value = float(row.get("value") or 0.0)
        if value < ACTIVITY_ON:
            continue
        start = float(row.get("start") or 0.0)
        end = start + 2.0
        items.append(_item(start, end, "Gesture activity", "gesture"))
    for ev in events.get("events") or []:
        if ev.get("type") != "gesture_stroke":
            continue
        items.append(
            _item(
                float(ev.get("t_start") or 0.0),
                float(ev.get("t_end") or 0.0),
                "Gesture stroke",
                "gesture",
            )
        )
    return items


def _audience_facing(series_gaze: dict[str, Any]) -> list[dict[str, Any]]:
    points = series_gaze.get("points") or []
    items: list[dict[str, Any]] = []
    start: float | None = None
    last_t = 0.0
    for point in points:
        t = float(point.get("t") or 0.0)
        value = point.get("value")
        facing = value is not None and float(value) >= 0.5
        if facing and start is None:
            start = t
        elif not facing and start is not None:
            items.append(_item(start, t, "Audience-facing", "facing"))
            start = None
        last_t = t
    if start is not None:
        items.append(_item(start, last_t + 1.0, "Audience-facing", "facing"))
    return items


def _smiles(
    events: dict[str, Any], expression_on: bool
) -> tuple[list[dict[str, Any]], bool]:
    if not expression_on:
        return [], False
    items: list[dict[str, Any]] = []
    for ev in events.get("events") or []:
        kind = str(ev.get("type") or "")
        if kind not in {"smile", "flat_face"}:
            continue
        label = "Smile" if kind == "smile" else "Flat face"
        items.append(
            _item(
                float(ev.get("t_start") or 0.0),
                float(ev.get("t_end") or 0.0),
                label,
                kind,
            )
        )
    return items, True


def _clt_story(
    content: dict[str, Any], lookup: dict[str, tuple[float, float]]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    story = content.get("story_impact") or {}
    for row in story.get("stories") or []:
        span = _span_for_seg(lookup, row.get("start_seg"), row.get("end_seg"))
        if span:
            items.append(_item(span[0], span[1], "Story", "story"))
    for row in story.get("clt_instances") or []:
        span = _span_for_seg(lookup, row.get("seg_id"), row.get("seg_id"))
        if span:
            quote = str(row.get("quote") or row.get("type") or "CLT")
            items.append(_item(span[0], span[1], quote, "clt"))
    return items


def _qa(
    content: dict[str, Any], lookup: dict[str, tuple[float, float]]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for pair in (content.get("qa") or {}).get("pairs") or []:
        span = _span_for_seg(
            lookup,
            pair.get("q_seg") or pair.get("start_seg"),
            pair.get("a_seg") or pair.get("end_seg"),
        )
        if span:
            items.append(_item(span[0], span[1], "Q&A", "qa"))
    return items


def build_timeline(output_dir: Path, duration_s: float | None = None) -> dict[str, Any]:
    """Assemble SPEC §8.4 lanes from session artifacts. Empty lanes are not invented scores."""
    dest = Path(output_dir)
    transcript = _read_json(dest / "transcript.json")
    content = _read_json(dest / "content.json")
    slides = _read_json(dest / "slides.json")
    pauses = _read_json(dest / "pauses.json")
    audio = _read_json(dest / "audio_metrics.json")
    gesture = _read_json(dest / "gesture_metrics.json")
    events = _read_json(dest / "vision_events.json")
    gaze_series = _read_json(dest / "series_gaze.json")
    consents = _read_json(dest / "consents.json")
    duration = float(
        duration_s or transcript.get("duration") or audio.get("duration_s") or 0.0
    )
    lookup = _seg_lookup(transcript)
    expr_on = bool(
        ((consents.get("purposes") or {}).get("expression_analysis") or {}).get(
            "granted"
        )
    )
    smiles, smiles_available = _smiles(events, expr_on)
    lanes = [
        _lane("sections", _sections(content, lookup), available=bool(content)),
        _lane("slides", _slides(slides), available=bool(slides.get("slides"))),
        _lane("fillers", _fillers(transcript), available=bool(transcript)),
        _lane(
            "long_pauses",
            _long_pauses(pauses),
            available=bool(pauses.get("pauses") is not None or pauses),
        ),
        _lane("rushing", _rushing(transcript), available=bool(transcript)),
        _lane("monotone", _monotone(audio), available=bool(audio)),
        _lane(
            "gestures",
            _gestures(gesture, events),
            available=bool(gesture or events.get("events")),
        ),
        _lane(
            "audience_facing",
            _audience_facing(gaze_series),
            available=bool(gaze_series.get("points")),
        ),
        _lane("smiles", smiles, available=smiles_available, opt_in=True),
        _lane("clt_story", _clt_story(content, lookup), available=bool(content)),
        _lane(
            "qa",
            _qa(content, lookup),
            available=bool((content.get("qa") or {}).get("pairs")),
        ),
    ]
    by_id = {lane["id"]: lane for lane in lanes}
    ordered = [by_id[lane_id] for lane_id in LANE_IDS]
    sprites_dir = dest / "sprites"
    sprite_count = (
        len(list(sprites_dir.glob("sprite_*.jpg"))) if sprites_dir.is_dir() else 0
    )
    return {
        "duration_s": round(max(duration, 0.0), 3),
        "sprite_interval_s": SPRITE_INTERVAL_S,
        "sprite_count": sprite_count,
        "lanes": ordered,
    }


def persist_timeline(
    output_dir: Path, duration_s: float | None = None
) -> dict[str, Any]:
    payload = build_timeline(output_dir, duration_s=duration_s)
    path = Path(output_dir) / "timeline.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def sprite_path(output_dir: Path, t: float) -> Path | None:
    idx = int(max(0.0, float(t)) // SPRITE_INTERVAL_S)
    candidate = Path(output_dir) / "sprites" / f"sprite_{idx:04d}.jpg"
    return candidate if candidate.is_file() else None
