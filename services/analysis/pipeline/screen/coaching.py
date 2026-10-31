"""online_flow_v1 coaching. Text only. A bad model answer never reaches the report."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from llm.verification import check_for_content_judgment, check_for_emotion_inference
from pipeline.prompt_versions import GUARD_SENTENCE, load_prompt_versions
from pipeline.screen.templates import templated_coaching

logger = logging.getLogger(__name__)

PROMPT_ID = "online_flow_v1"
PROMPT_VERSION = "1.0.1"
IMAGE_KEYS = {"image", "frame", "keyframe", "thumbnail", "base64"}
_MAX_SCREENS = 40
_MAX_WORDS = 600


def image_keys(value: Any, prefix: str = "") -> list[str]:
    """Keys that would carry a picture. The model payload must have none."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in IMAGE_KEYS or "base64" in str(key).lower():
                found.append(path)
            found.extend(image_keys(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(image_keys(item, f"{prefix}[{index}]"))
    return found


def _strip_images(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _strip_images(item)
            for key, item in value.items()
            if str(key).lower() not in IMAGE_KEYS and "base64" not in str(key).lower()
        }
    if isinstance(value, list):
        return [_strip_images(item) for item in value]
    return value


def _words(text: str, limit: int) -> str:
    parts = [part for part in str(text or "").split() if part]
    return " ".join(parts[:limit])


def _narration_for(segment: dict[str, Any], transcript: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    start = float(segment.get("t_start") or 0)
    end = float(segment.get("t_end") or start)
    rows: list[dict[str, Any]] = []
    words = 0
    for segment_row in (transcript or {}).get("segments") or []:
        seg_start = float(segment_row.get("start") or 0)
        seg_end = float(segment_row.get("end") or seg_start)
        if seg_end < start or seg_start > end:
            continue
        text = _words(str(segment_row.get("text") or ""), _MAX_WORDS - words)
        if not text:
            continue
        words += len(text.split())
        rows.append(
            {
                "seg": str(segment_row.get("id") or ""),
                "t": seg_start,
                "text": text,
            }
        )
        if words >= _MAX_WORDS:
            break
    return rows


def select_screens(segments: list[dict[str, Any]], limit: int = _MAX_SCREENS) -> list[dict[str, Any]]:
    if len(segments) <= limit:
        return list(segments)
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(segment: dict[str, Any]) -> None:
        key = str(segment.get("id") or id(segment))
        if key in seen:
            return
        seen.add(key)
        chosen.append(segment)

    add(segments[0])
    add(segments[-1])
    flagged = sorted(segments, key=lambda row: len(row.get("flags") or []), reverse=True)
    for segment in flagged:
        if len(chosen) >= limit:
            break
        if segment.get("flags"):
            add(segment)
    for segment in segments:
        if len(chosen) >= limit:
            break
        add(segment)
    chosen.sort(key=lambda row: float(row.get("t_start") or 0))
    return chosen


def build_online_flow_payload(
    *,
    delivery_mode: str,
    language: str,
    screen_doc: Optional[dict[str, Any]],
    transcript: Optional[dict[str, Any]],
    camera: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Bounded text payload. Picture paths are removed before the model sees it."""
    document = screen_doc or {}
    metrics: dict[str, Any] = {}
    for row in document.get("metrics") or []:
        if row.get("applicable") and row.get("value") is not None:
            metrics[str(row.get("id"))] = row.get("value")
    screens = []
    for segment in select_screens(list(document.get("segments") or [])):
        shared = ((segment.get("narration") or {}).get("shared_terms")) or []
        screens.append(
            {
                "id": segment.get("id"),
                "t_start": segment.get("t_start"),
                "t_end": segment.get("t_end"),
                "type": segment.get("type"),
                "dwell_s": segment.get("dwell_s"),
                "ocr_word_count": segment.get("ocr_word_count"),
                "flags": list(segment.get("flags") or []),
                "on_screen_terms": list(shared)[:12],
                "narration": _narration_for(segment, transcript),
            }
        )
    events = []
    for event in (document.get("events") or [])[:40]:
        events.append(
            {
                "id": event.get("id"),
                "kind": event.get("kind"),
                "t": event.get("t"),
                "dur_s": event.get("dur_s"),
            }
        )
    camera_view = None
    if isinstance(camera, dict) and camera:
        camera_view = _strip_images(
            {
                key: value
                for key, value in camera.items()
                if isinstance(value, (str, int, float, list, dict)) and key not in {"samples", "frames"}
            }
        )
    payload = {
        "mode": delivery_mode,
        "language": language or "en",
        "duration_s": float((transcript or {}).get("duration") or document.get("screen_visible_s") or 0),
        "instructions": _prompt_body(),
        "metrics": metrics,
        "screens": screens,
        "events": events,
    }
    if camera_view:
        payload["camera"] = camera_view
    cleaned = _strip_images(payload)
    if image_keys(cleaned):
        raise ValueError("online flow payload still has a picture key")
    return cleaned


def _prompt_body() -> str:
    path = Path(__file__).resolve().parents[2] / "prompts" / "online_flow_v1.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return GUARD_SENTENCE


def _hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _item_text(item: dict[str, Any]) -> str:
    parts = []
    for key in ("title", "detail", "how"):
        if item.get(key):
            parts.append(str(item[key]))
    return " ".join(parts)


def _judged(text: str, language: str) -> bool:
    flagged, _terms = check_for_content_judgment(text, language)
    if flagged:
        return True
    emotion, _found = check_for_emotion_inference(text, language)
    return emotion


def _keep_items(items: Any, language: str) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    dropped = 0
    if not isinstance(items, list):
        return kept, 1 if items else 0
    for item in items:
        if not isinstance(item, dict):
            dropped += 1
            continue
        if _judged(_item_text(item), language):
            dropped += 1
            continue
        kept.append(item)
    return kept, dropped


def _complete(observations: list, drills: list, strengths: list) -> bool:
    return 3 <= len(observations) <= 6 and len(drills) == 3 and 1 <= len(strengths) <= 3


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    observations = []
    for item in data.get("observations") or []:
        if not isinstance(item, dict):
            continue
        observations.append(
            {
                "title": str(item.get("title") or "")[:80],
                "detail": str(item.get("detail") or "")[:400],
                "t": float(item.get("t") or 0),
                "evidence_ids": [str(value) for value in (item.get("evidence_ids") or [])][:4],
            }
        )
    drills = []
    for item in data.get("drills") or []:
        if not isinstance(item, dict):
            continue
        drills.append(
            {
                "title": str(item.get("title") or "")[:80],
                "how": str(item.get("how") or "")[:400],
                "practice_time_min": float(item.get("practice_time_min") or 10),
                "targets_metric": str(item.get("targets_metric") or ""),
            }
        )
    strengths = []
    for item in data.get("strengths") or []:
        if not isinstance(item, dict):
            continue
        strengths.append(
            {
                "title": str(item.get("title") or "")[:80],
                "evidence_ids": [str(value) for value in (item.get("evidence_ids") or [])][:4],
            }
        )
    return {"observations": observations, "drills": drills, "strengths": strengths}


def _filter_model(data: Any, language: str) -> tuple[Optional[dict[str, Any]], int, int]:
    if not isinstance(data, dict):
        text = data if isinstance(data, str) else ""
        dropped = 1 if text else 1
        if text and _judged(text, language):
            logger.warning("content_judgment online_flow_v1 dropped_items=%s", 1)
        return None, dropped, dropped
    observations, dropped_o = _keep_items(data.get("observations"), language)
    drills, dropped_d = _keep_items(data.get("drills"), language)
    strengths, dropped_s = _keep_items(data.get("strengths"), language)
    dropped = dropped_o + dropped_d + dropped_s
    original = dropped + len(observations) + len(drills) + len(strengths)
    if dropped:
        logger.warning("content_judgment online_flow_v1 dropped_items=%s", dropped)
    if original and dropped / original > 0.5:
        return None, dropped, original
    normalized = _normalize({"observations": observations, "drills": drills, "strengths": strengths})
    if not _complete(normalized["observations"], normalized["drills"], normalized["strengths"]):
        return None, dropped, original
    return normalized, dropped, original


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _ask(client: Any, payload: dict[str, Any], schema: dict[str, Any]) -> Any:
    response = client.generate_structured(
        prompt_id=PROMPT_ID,
        inputs=payload,
        schema=schema,
        temperature=0.2,
    )
    return getattr(response, "data", response)


def run_online_flow(
    *,
    output_dir: Path,
    delivery_mode: str,
    language: str = "en",
    client: Any = None,
) -> dict[str, Any]:
    """Write online_flow.json. Never raises. Stage sessions are skipped."""
    output_dir = Path(output_dir)
    if delivery_mode == "stage":
        return {"skipped": True, "latency_s": 0.0, "source": None, "fallback": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    screen_doc = _read_json(output_dir / "screen_flow.json") or {}
    transcript = _read_json(output_dir / "transcript.json") or {}
    camera = _read_json(output_dir / "camera_metrics.json")
    try:
        payload = build_online_flow_payload(
            delivery_mode=delivery_mode,
            language=language,
            screen_doc=screen_doc,
            transcript=transcript,
            camera=camera,
        )
    except Exception:
        logger.info("online flow payload skipped", exc_info=True)
        payload = {
            "mode": delivery_mode,
            "language": language,
            "instructions": GUARD_SENTENCE,
            "metrics": {},
            "screens": [],
            "events": [],
        }
    digest = _hash(payload)
    existing = _read_json(output_dir / "online_flow.json")
    if existing and existing.get("input_hash") == digest and existing.get("observations"):
        return {
            "skipped": False,
            "latency_s": float(existing.get("latency_s") or 0),
            "source": existing.get("source"),
            "fallback": bool(existing.get("fallback")),
            "cached": True,
        }

    version = load_prompt_versions().get(PROMPT_ID, PROMPT_VERSION)
    schema_path = Path(__file__).resolve().parents[2] / "llm" / "schemas" / "online_flow_v1.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        schema = {"type": "object"}

    started = time.perf_counter()
    source = "template"
    fallback = True
    body = templated_coaching(
        list(screen_doc.get("metrics") or []),
        language=language,
        evidence_id=str((payload.get("screens") or [{"id": "screen"}])[0].get("id") or "screen"),
    )
    provider = str(getattr(client, "provider_name", "") or "local")
    if client is None:
        try:
            from llm.client import LLMClient

            client = LLMClient(settings_path=output_dir / "llm_settings.json")
            provider = str(getattr(client, "provider_name", "") or provider)
        except Exception:
            logger.info("online flow model client unavailable")
            client = None

    def accept(data: Any) -> bool:
        """True when the answer was dropped or incomplete and should be asked once more."""
        nonlocal body, source, fallback
        kept, _dropped, _original = _filter_model(data, language)
        if kept is None:
            return True
        body = kept
        source = PROMPT_ID
        fallback = False
        return False

    if client is not None:
        try:
            first = _ask(client, payload, schema)
            if accept(first):
                reminder = dict(payload)
                reminder["reminder"] = GUARD_SENTENCE
                accept(_ask(client, reminder, schema))
        except Exception:
            logger.info("online flow model call failed", exc_info=True)
            source = "template"
            fallback = True
            body = templated_coaching(list(screen_doc.get("metrics") or []), language=language)
    latency_s = round(time.perf_counter() - started, 4)
    document = {
        "source": source if not fallback else "template",
        "fallback": fallback,
        "prompt_version": version,
        "content_judgment": False,
        "latency_s": latency_s,
        "input_hash": digest,
        "provider": provider,
        "observations": body["observations"],
        "drills": body["drills"],
        "strengths": body["strengths"],
    }
    blob = json.dumps(document, ensure_ascii=False)
    if "incorrect" in blob.lower():
        safe = templated_coaching(list(screen_doc.get("metrics") or []), language=language)
        document["observations"] = safe["observations"]
        document["drills"] = safe["drills"]
        document["strengths"] = safe["strengths"]
        document["source"] = "template"
        document["fallback"] = True
    (output_dir / "online_flow.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "skipped": False,
        "latency_s": latency_s,
        "source": document["source"],
        "fallback": document["fallback"],
        "cached": False,
        "provider": provider,
    }
