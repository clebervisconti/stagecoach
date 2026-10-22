"""Fusion + scoring stage (issue #30, SPEC §6.8).

Maps existing metrics.json, audio features, transcript, and content_llm
outputs onto scoring-config v1.1.0 (mode=stage by default). Missing inputs
make a category N/A; scores are never invented.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pipeline.consent import decide_vision, video_category_na_reason
from pipeline.na_codes import infer_na_code
from pipeline.partial import vision_failed_na_reason, vision_failed_warning

logger = logging.getLogger(__name__)

STAGE_VERSION = "1.0.0"
SCORING_CONFIG_VERSION = "1.1.0"
PIPELINE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.1.0"

VIDEO_CATEGORIES = {
    "visual_aids": "No slides were detected and no deck was uploaded.",
    "gestures_body": "Vision stage was not run; body metrics need a visible person.",
    "eye_contact": "Vision stage was not run; gaze metrics need a visible face.",
    "facial_affect": "Expression analysis is off and vision was not run.",
}
CONTENT_TEXT_CATEGORIES = {
    "core_message",
    "structure",
    "storytelling",
    "audience_adaptation",
    "opening_close",
    "clarity",
    "impact",
}
QA_NOT_IN_SLOT_REASON = "This session did not include a Q&A segment."
ONLINE_STAGE_NA = {
    "screen_flow": "Screen flow is not scored for on-stage sessions.",
    "on_camera_presence": "On-camera presence is not scored for on-stage sessions.",
    "online_engagement": "This category is not scored for on-stage sessions.",
    "production_quality": "Production quality is not scored for on-stage sessions.",
}
ONLINE_NOT_IN_PHASE = {
    "screen_flow": "Coming soon. We found your screen and kept it ready for this.",
    "on_camera_presence": "Coming soon.",
    "online_engagement": "Coming soon.",
}
CORE_DELIVERY_IDS = (
    "pace_pausing",
    "vocal_variety",
    "fluency",
    "energy_presence",
    "structure",
    "clarity",
    "opening_close",
)

PILLAR_OF = {
    "core_message": "message",
    "structure": "message",
    "opening_close": "message",
    "clarity": "message",
    "storytelling": "story_impact",
    "audience_adaptation": "story_impact",
    "impact": "story_impact",
    "visual_aids": "visuals",
    "pace_pausing": "voice",
    "vocal_variety": "voice",
    "fluency": "voice",
    "gestures_body": "body",
    "eye_contact": "body",
    "facial_affect": "body",
    "energy_presence": "presence_time",
    "time_management": "presence_time",
    "qa": "presence_time",
    "screen_flow": "visuals",
    "on_camera_presence": "body",
    "online_engagement": "presence_time",
    "production_quality": "production",
}

CLAIM_TYPE_LEVEL = {"none": 1, "topic": 2, "vague_claim": 3, "claim": 5}


def _walk_packages() -> list[Path]:
    """Locate packages/ without assuming a repo-relative depth.

    In Docker the worker lives at /app/pipeline/stages/..., so parents[4]
    raises IndexError. Prefer the compose mount at /packages.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for path in (Path("/packages"),):
        if path.exists() and path not in seen:
            found.append(path)
            seen.add(path)
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        candidate = parent / "packages"
        if candidate.exists() and candidate not in seen:
            found.append(candidate)
            seen.add(candidate)
    return found


def _ensure_scoring_path() -> None:
    for packages in _walk_packages():
        path = packages / "scoring"
        if (path / "scoring").exists() or (path / "pyproject.toml").exists():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            return


def _packages_dir() -> Path:
    for path in _walk_packages():
        if (path / "scoring-config").exists() or (path / "schemas").exists():
            return path
    return Path("/packages")


def _load_schema(packages: Path | None = None) -> dict[str, Any]:
    path = (packages or _packages_dir()) / "schemas" / "analysis_result.v1.json"
    return json.loads(path.read_text())


def _session_uuid(session_id: str) -> str:
    try:
        return str(uuid.UUID(session_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"stagecoach:session:{session_id}"))


def _read_json(path: Optional[Path]) -> Optional[dict[str, Any]]:
    if path is None or not path.exists():
        return None
    from pipeline.vision.crypto import load_json_object

    loaded = load_json_object(path)
    if loaded is not None:
        return loaded
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _first_number(*values: Any) -> Optional[float]:
    """Return the first value that is not None. 0.0 is a real measurement."""
    for value in values:
        if value is not None:
            return float(value)
    return None


def _ratio_from(payload: Optional[dict[str, Any]], key: str = "face_visible_ratio") -> Optional[float]:
    if not payload or key not in payload or payload[key] is None:
        return None
    return float(payload[key])


def _normalize_language(value: Optional[str]) -> str:
    if value and value.startswith("pt"):
        return "pt-BR"
    return "en"


def _normalize_source(raw: str) -> str:
    if raw in {"H", "heuristic"}:
        return "heuristic"
    if raw.startswith("S") and raw[1:].split("_")[0].isdigit():
        return "S" + raw[1:].split("_")[0] if "_" in raw else raw
    return "heuristic"


def _category_sources(config: dict[str, Any], category_id: str) -> list[str]:
    sources = []
    for item in config["categories"].get(category_id, {}).get("sources", []):
        token = _normalize_source(str(item))
        if token not in sources and (token == "heuristic" or token.startswith("S")):
            sources.append(token)
    return sources or ["heuristic"]


def _speech_stats(transcript: dict[str, Any]) -> dict[str, float]:
    words: list[dict[str, Any]] = []
    for segment in transcript.get("segments", []):
        segs_words = segment.get("words") or []
        if segs_words:
            words.extend(segs_words)
        else:
            tokens = str(segment.get("text") or "").split()
            start = float(segment.get("start") or 0)
            end = float(segment.get("end") or start)
            step = (end - start) / max(len(tokens), 1)
            for i, token in enumerate(tokens):
                words.append(
                    {
                        "word": token,
                        "start": start + i * step,
                        "end": start + (i + 1) * step,
                        "probability": float(transcript.get("mean_word_probability") or 0),
                    }
                )
    if not words:
        duration = float(transcript.get("duration") or 0)
        return {
            "speech_words": 0,
            "speech_seconds": 0,
            "opening_words": 0,
            "closing_words": 0,
            "duration_s": duration,
            "mean_word_prob": float(transcript.get("mean_word_probability") or 0),
        }
    start = min(float(w.get("start") or 0) for w in words)
    end = max(float(w.get("end") or 0) for w in words)
    opening = [w for w in words if float(w.get("start") or 0) <= start + 60]
    closing = [w for w in words if float(w.get("end") or 0) >= end - 90]
    return {
        "speech_words": float(len(words)),
        "speech_seconds": max(0.0, end - start),
        "opening_words": float(len(opening)),
        "closing_words": float(len(closing)),
        "duration_s": float(transcript.get("duration") or (end - start)),
        "mean_word_prob": float(transcript.get("mean_word_probability") or 0),
    }


def _min_evidence_ok(category_id: str, config: dict[str, Any], stats: dict[str, float], extras: dict[str, Any]) -> tuple[bool, Optional[str]]:
    rules = config["categories"].get(category_id, {}).get("min_evidence", {})
    for key, threshold in rules.items():
        if key == "speech_words" and stats["speech_words"] < threshold:
            return False, f"Need at least {threshold} transcribed words; found {int(stats['speech_words'])}."
        if key == "speech_seconds" and stats["speech_seconds"] < threshold:
            return False, f"Need at least {threshold}s of speech; found {stats['speech_seconds']:.1f}s."
        if key == "opening_words" and stats["opening_words"] < threshold:
            return False, f"Opening window has fewer than {threshold} words."
        if key == "closing_words" and stats["closing_words"] < threshold:
            return False, f"Closing window has fewer than {threshold} words."
        if key == "asr_mean_word_prob" and stats["mean_word_prob"] < threshold:
            return False, f"ASR mean word probability {stats['mean_word_prob']:.2f} is below {threshold}."
        if key == "voiced_seconds" and extras.get("voiced_s", 0) < threshold:
            return False, f"Need at least {threshold}s of voiced speech."
        if key == "slot_length_provided" and threshold and not extras.get("slot_min"):
            return False, "No slot length was provided, so time management is unavailable."
        if key == "qa_detected" and threshold and not extras.get("qa_detected"):
            return False, "No Q&A was detected."
        if key == "question_count" and extras.get("question_count", 0) < threshold:
            return False, "Fewer than one question was detected."
        if key == "slides_detected":
            found = extras.get("slides_detected") or 0
            if found < threshold:
                return False, "No slides were detected and no deck was uploaded."
            continue
        if key == "person_visible_ratio":
            ratio = float(extras.get("person_visible_ratio") or 0.0)
            if ratio < float(threshold):
                return False, f"Person visible in {ratio:.0%} of frames; need {float(threshold):.0%}."
        if key == "hands_visible_ratio":
            # Hand-based gb_* metrics use the 40% gate in gesture functions (SPEC §4.4.12).
            continue
        if key == "face_visible_ratio":
            ratio = float(extras.get("face_visible_ratio") or 0.0)
            if ratio < float(threshold):
                return False, f"Face visible in {ratio:.0%} of frames; need {float(threshold):.0%}."
        if key == "face_px_median":
            px = float(extras.get("face_px_median") or 0.0)
            if px < float(threshold):
                return False, f"Median face height {px:.0f} px is below {threshold}."
        if key == "screen_visible_s" and float(extras.get("screen_visible_s") or 0) < float(threshold):
            return False, f"Need at least {threshold}s of visible screen."
        if key == "screen_segments" and int(extras.get("screen_segments") or 0) < int(threshold):
            return False, f"Need at least {threshold} screen segments."
        if key == "camera_visible_s" and float(extras.get("camera_visible_s") or 0) < float(threshold):
            return False, f"Need at least {threshold}s of visible camera."
        if key == "has_audio" and threshold and not extras.get("has_audio", True):
            return False, "No audio track, so production quality is unavailable."
    return True, None


def _production_metrics_from_payload(
    payload: Optional[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not payload:
        return []
    defs = (config.get("categories") or {}).get("production_quality", {}).get("metrics") or {}
    items: list[dict[str, Any]] = []
    for row in payload.get("metrics") or []:
        metric_id = row.get("id")
        if metric_id not in defs or row.get("value") is None or row.get("applicable") is False:
            continue
        metric_def = defs[metric_id]
        items.append(
            {
                "id": metric_id,
                "category_id": "production_quality",
                "raw_value": row["value"],
                "unit": row.get("unit") or metric_def.get("unit") or "",
                "confidence": float(row.get("confidence") or 0.85),
                "weight": float(metric_def.get("weight") or 0),
                "basis": {"kind": "heuristic", "source": str(row.get("source") or "H")},
            }
        )
    return items


def _core_delivery(categories_out: list[dict[str, Any]]) -> dict[str, Any]:
    members = [
        row
        for row in categories_out
        if row["id"] in CORE_DELIVERY_IDS and row.get("applicable") and row.get("score") is not None
    ]
    if len(members) < 4:
        return {"score": None, "confidence": None, "categories": list(CORE_DELIVERY_IDS)}
    score = int(round(sum(float(row["score"]) for row in members) / len(members)))
    conf = sum(float(row.get("confidence") or 0) for row in members) / len(members)
    return {"score": score, "confidence": conf, "categories": [row["id"] for row in members]}


def _layout_summary(output_dir: Path) -> Optional[dict[str, Any]]:
    payload = _read_json(output_dir / "layout.json")
    if not payload:
        return None
    segments = payload.get("segments") or []
    kinds = [str(seg.get("kind")) for seg in segments if seg.get("kind")]
    duration = float((payload.get("frame") or {}).get("duration_s") or 0) or 1.0
    camera_s = 0.0
    screen_s = 0.0
    for seg in segments:
        span = max(0.0, float(seg.get("t_end") or 0) - float(seg.get("t_start") or 0))
        roles = {reg.get("role") for reg in seg.get("regions") or []}
        if "camera" in roles:
            camera_s += span
        if "screen" in roles:
            screen_s += span
    return {
        "kinds": kinds,
        "camera_visible_ratio": camera_s / duration,
        "screen_visible_ratio": screen_s / duration,
        "version": int(payload.get("version") or 1),
        "status": str(payload.get("status") or "detected"),
    }


def _category_na_code(reason: Optional[str], category_id: str) -> Optional[str]:
    return infer_na_code(reason, category_id=category_id)


def _seg_time(transcript: dict[str, Any], seg_id: Optional[str]) -> Optional[float]:
    if not seg_id:
        return None
    try:
        index = int(seg_id[1:]) - 1
    except (TypeError, ValueError):
        return None
    segments = transcript.get("segments") or []
    if 0 <= index < len(segments):
        return float(segments[index].get("start") or 0)
    return None


def _seg_end(transcript: dict[str, Any], seg_id: Optional[str]) -> Optional[float]:
    if not seg_id:
        return None
    try:
        index = int(seg_id[1:]) - 1
    except (TypeError, ValueError):
        return None
    segments = transcript.get("segments") or []
    if 0 <= index < len(segments):
        return float(segments[index].get("end") or 0)
    return None


def _llm_confidence(
    block: dict[str, Any],
    asr_c: float,
    *,
    evidence_path: str | None = None,
) -> float:
    """Confidence for one content metric.

    A failed quote check belongs to that evidence list. It must not zero a
    level the model agreed on, such as audience fit or clarity.
    """
    meta = block.get("consistency_metadata") or {}
    agreements = [float(v.get("agreement", 0)) for v in meta.values() if isinstance(v, dict)]
    agreement = sum(agreements) / len(agreements) if agreements else 0.7
    validity = 1.0
    if evidence_path:
        entry = (block.get("verification_metadata") or {}).get(evidence_path) or {}
        if isinstance(entry, dict) and "confidence_factor" in entry:
            validity = float(entry["confidence_factor"])
    return max(0.0, min(1.0, agreement * validity * max(asr_c, 0.4)))


def _metric_payload(
    *,
    metric_id: str,
    category_id: str,
    raw_value: Any,
    confidence: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    metric_def = config["categories"][category_id]["metrics"][metric_id]
    basis = metric_def.get("basis", {"kind": "heuristic", "source": "H"})
    source = str(basis.get("source", "H"))
    kind = str(basis.get("kind", "heuristic"))
    if source == "H":
        source = "heuristic"
        if kind == "research":
            kind = "heuristic"
    return {
        "id": metric_id,
        "category_id": category_id,
        "raw_value": raw_value,
        "unit": metric_def.get("unit", ""),
        "confidence": confidence,
        "basis": {"kind": kind if kind in {"research", "heuristic", "llm_judgment"} else "heuristic", "source": source},
        "weight": metric_def.get("weight", 0.0),
    }


def _content_metrics(
    content: dict[str, Any],
    transcript: dict[str, Any],
    stats: dict[str, float],
    asr_c: float,
    config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Extract only fields that content_llm actually produced."""
    out: dict[str, list[dict[str, Any]]] = {cid: [] for cid in config["categories"]}
    duration = max(stats["duration_s"], 1.0)
    message = content.get("message") or {}
    outline = content.get("outline") or {}
    story = content.get("story_impact") or {}
    audience = content.get("audience_clarity") or {}
    open_close = content.get("open_close") or {}
    qa = content.get("qa") or {}

    def add(
        category: str,
        metric_id: str,
        raw: Any,
        block: dict[str, Any],
        *,
        evidence_path: str | None = None,
    ) -> None:
        if raw is None:
            return
        out[category].append(
            _metric_payload(
                metric_id=metric_id,
                category_id=category,
                raw_value=raw,
                confidence=_llm_confidence(block, asr_c, evidence_path=evidence_path),
                config=config,
            )
        )

    if message and not message.get("insufficient_evidence"):
        core = message.get("core_message")
        if isinstance(core, dict):
            add("core_message", "cm_message_identifiable", core.get("level"), message)
            claim = core.get("claim_type")
            if claim in CLAIM_TYPE_LEVEL:
                add("core_message", "cm_claim_not_topic", CLAIM_TYPE_LEVEL[claim], message)
            first = _seg_time(transcript, (core.get("seg_ids") or [None])[0])
            if first is not None:
                add("core_message", "cm_time_to_message_s", first, message)
        add("core_message", "cm_reinforcement_count", len(message.get("reinforcements") or []), message)
        cta = message.get("cta") or {}
        if cta.get("specificity_level") is not None:
            add("core_message", "cm_cta_specificity", cta.get("specificity_level"), message)
            add("impact", "imp_cta_strength", cta.get("specificity_level"), message)

        bluf = message.get("bluf") or {}
        if "present" in bluf:
            t = _seg_time(transcript, bluf.get("seg_id"))
            if bluf.get("present") and t is not None:
                label = "in_first_10pct" if t <= 0.10 * duration else "by_25pct" if t <= 0.25 * duration else "later"
            else:
                label = "later"
            add("clarity", "cl_bluf", label, message)

    if outline and not outline.get("insufficient_evidence"):
        add("structure", "st_outline_clarity", outline.get("outline_clarity_level"), outline)
        if outline.get("main_points") is not None:
            add("structure", "st_main_points_count", outline.get("main_points"), outline)
        sections = outline.get("sections") or []
        boundaries = max(len(sections) - 1, 1)
        add("structure", "st_signposts_per_boundary", len(outline.get("signposts") or []) / boundaries, outline)
        add("structure", "st_recap_present", "present" if outline.get("recap_seg") else "absent", outline)

    if story and not story.get("insufficient_evidence"):
        complete = [
            s
            for s in (story.get("stories") or [])
            if s.get("tied_to_message") and s.get("character") and s.get("conflict") and s.get("resolution")
        ]
        per_20 = len(complete) * (1200.0 / duration)
        add("storytelling", "sto_story_units", per_20, story)
        success = story.get("success_profile") or {}
        add("storytelling", "sto_concreteness", success.get("concrete_level"), story)
        add("storytelling", "sto_contrast_moves_per_10min", len(story.get("contrasts") or []) * (600.0 / duration), story)
        add("storytelling", "sto_novelty_moment", "present" if story.get("memorable_moment") else "absent", story)
        clt = story.get("clt_instances") or []
        add("impact", "imp_clt_density", len(clt) * (300.0 / duration), story)
        add("impact", "imp_clt_diversity", len({item.get("type") for item in clt if item.get("type")}), story)
        levels = [
            success.get(k)
            for k in (
                "simple_level",
                "unexpected_level",
                "concrete_level",
                "credible_level",
                "emotional_level",
                "stories_level",
            )
            if isinstance(success.get(k), (int, float))
        ]
        if levels:
            add("impact", "imp_success_profile", sum(levels) / len(levels), story)

    if audience and not audience.get("insufficient_evidence"):
        add("audience_adaptation", "aud_depth_fit", audience.get("audience_fit_level"), audience)
        undefined = [j for j in (audience.get("jargon") or []) if j.get("defined") is False]
        add("audience_adaptation", "aud_jargon_undefined_per_10min", len(undefined) * (600.0 / duration), audience)
        sentences = max(
            1,
            sum(str(seg.get("text") or "").count(".") + str(seg.get("text") or "").count("?") + 1 for seg in transcript.get("segments") or []),
        )
        add(
            "audience_adaptation",
            "aud_speaker_centric_ratio",
            len(audience.get("speaker_centric_phrases") or []) / sentences,
            audience,
        )
        claims = audience.get("claims") or []
        if claims:
            supported = sum(1 for c in claims if c.get("support_type") not in {None, "none"})
            add(
                "clarity",
                "cl_claims_supported_ratio",
                supported / len(claims),
                audience,
                evidence_path="claims",
            )
        add("clarity", "cl_precision_llm", audience.get("clarity_level"), audience)
        vague = audience.get("vagueness") or []
        words = max(stats["speech_words"], 1)
        add("clarity", "cl_vagueness_per_100w", len(vague) * (100.0 / words), audience)
        red_spans = audience.get("redundancy_spans") or []
        red_s = 0.0
        for span in red_spans:
            ids = span.get("seg_ids") or []
            if len(ids) >= 2:
                a = _seg_time(transcript, ids[0])
                b = _seg_end(transcript, ids[-1])
                if a is not None and b is not None:
                    red_s += max(0.0, b - a)
        add("clarity", "cl_redundancy_ratio", red_s / duration, audience)

    if open_close and not open_close.get("insufficient_evidence"):
        opening = open_close.get("opening") or {}
        closing = open_close.get("closing") or {}
        add("opening_close", "oc_hook_quality", opening.get("hook_level"), open_close)
        throat = _seg_end(transcript, opening.get("throat_clearing_end_seg"))
        if opening.get("throat_clearing_end_seg") is None:
            add("opening_close", "oc_throat_clearing_s", 0.0, open_close)
        elif throat is not None:
            add("opening_close", "oc_throat_clearing_s", throat, open_close)
        if "message_restated" in closing:
            add("opening_close", "oc_close_recap", "clear" if closing.get("message_restated") else "absent", open_close)
        add("opening_close", "oc_ending_quality", closing.get("closing_level"), open_close)

    # Sentence metrics from the existing transcript (not invented).
    texts = [str(seg.get("text") or "").strip() for seg in transcript.get("segments") or []]
    sentences = [t for t in texts if t]
    if sentences:
        lengths = [len(s.split()) for s in sentences]
        add("clarity", "cl_mean_sentence_words", sum(lengths) / len(lengths), audience or message or {})
        add("clarity", "cl_long_sentence_ratio", sum(1 for n in lengths if n > 30) / len(lengths), audience or message or {})

    if qa and not qa.get("insufficient_evidence") and qa.get("pairs"):
        pairs = qa["pairs"]
        extras_q = True  # used by caller via qa block presence
        _ = extras_q
        first = [p for p in pairs if p.get("answer_first")]
        add("qa", "qa_answer_first_ratio", len(first) / len(pairs), qa)
        lengths = [float(p.get("answer_length_s")) for p in pairs if p.get("answer_length_s") is not None]
        if lengths:
            lengths.sort()
            mid = lengths[len(lengths) // 2]
            add("qa", "qa_answer_length_s_median", mid, qa)
        add("qa", "qa_structure_llm", qa.get("structure_level"), qa)
        bridged = [p for p in pairs if p.get("bridges_back")]
        add("qa", "qa_bridge_back_ratio", len(bridged) / len(pairs), qa)
        add("qa", "qa_composure_llm", qa.get("composure_level"), qa)

    return out


def _metrics_from_bundle(
    bundle: dict[str, Any],
    config: dict[str, Any],
    music_flag: bool,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {cid: [] for cid in config["categories"]}
    for metric_id, payload in (bundle.get("metrics") or {}).items():
        if not payload or payload.get("value") is None or payload.get("applicable") is False:
            continue
        category_id = None
        for cid, cdef in config["categories"].items():
            if metric_id in cdef.get("metrics", {}):
                category_id = cid
                break
        if category_id is None:
            continue
        if category_id == "vocal_variety" and music_flag:
            continue
        metric_def = config["categories"][category_id]["metrics"][metric_id]
        if not (
            metric_def.get("llm_level")
            or "curve" in metric_def
            or "context_curves" in metric_def
            or "mode_curves" in metric_def
            or "mapping" in metric_def
        ):
            continue
        grouped[category_id].append(
            _metric_payload(
                metric_id=metric_id,
                category_id=category_id,
                raw_value=payload["value"],
                confidence=float(payload.get("confidence") or 0),
                config=config,
            )
        )
    return grouped


def _energy_from_audio(
    audio: dict[str, Any],
    config: dict[str, Any],
    confidence: float,
) -> list[dict[str, Any]]:
    """Backward-compatible wrapper; prefer compute_energy_metrics."""
    from pipeline.energy import compute_energy_metrics

    payload = compute_energy_metrics(audio=audio)
    return _energy_metrics_from_payload(payload, config, confidence)


def _energy_metrics_from_payload(
    payload: Optional[dict[str, Any]],
    config: dict[str, Any],
    confidence: float,
) -> list[dict[str, Any]]:
    """Map energy_metrics.json onto scoring-config energy_presence ids. No SER."""
    if not payload:
        return []
    out: list[dict[str, Any]] = []
    allowed = config["categories"]["energy_presence"]["metrics"]
    for metric_id, row in (payload.get("metrics") or {}).items():
        if metric_id not in allowed:
            continue
        if not row or row.get("applicable") is False or row.get("value") is None:
            continue
        out.append(
            _metric_payload(
                metric_id=metric_id,
                category_id="energy_presence",
                raw_value=row["value"],
                confidence=min(confidence, float(row.get("confidence") or 0.5)),
                config=config,
            )
        )
    return out


def _visual_aids_from_payload(payload: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Map visual_aids_metrics.json onto scoring-config visual_aids ids."""
    out: list[dict[str, Any]] = []
    allowed = config["categories"]["visual_aids"]["metrics"]
    for metric_id, row in (payload.get("metrics") or {}).items():
        if metric_id not in allowed:
            continue
        if not row or row.get("applicable") is False or row.get("value") is None:
            continue
        out.append(
            _metric_payload(
                metric_id=metric_id,
                category_id="visual_aids",
                raw_value=row["value"],
                confidence=float(row.get("confidence") or 0.5),
                config=config,
            )
        )
    return out


def _section_boundaries(content: Optional[dict[str, Any]], transcript: dict[str, Any]) -> list[float]:
    outline = (content or {}).get("outline") or {}
    bounds: list[float] = []
    for section in outline.get("sections") or []:
        t = _seg_time(transcript, section.get("start_seg"))
        if t is not None:
            bounds.append(t)
    return bounds


def _body_metrics_from_payload(payload: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Map gesture_metrics.json onto scoring-config gestures_body ids."""
    out: list[dict[str, Any]] = []
    allowed = config["categories"]["gestures_body"]["metrics"]
    for metric_id, row in (payload.get("metrics") or {}).items():
        if metric_id not in allowed:
            continue
        if not row or row.get("applicable") is False or row.get("value") is None:
            continue
        out.append(
            _metric_payload(
                metric_id=metric_id,
                category_id="gestures_body",
                raw_value=row["value"],
                confidence=float(row.get("confidence") or 0.5),
                config=config,
            )
        )
    return out


def _gaze_metrics_from_payload(payload: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Map gaze_metrics.json onto scoring-config eye_contact ids. Head-orientation proxy only."""
    out: list[dict[str, Any]] = []
    allowed = config["categories"]["eye_contact"]["metrics"]
    for metric_id, row in (payload.get("metrics") or {}).items():
        if metric_id not in allowed:
            continue
        if not row or row.get("applicable") is False or row.get("value") is None:
            continue
        out.append(
            _metric_payload(
                metric_id=metric_id,
                category_id="eye_contact",
                raw_value=row["value"],
                confidence=float(row.get("confidence") or 0.5),
                config=config,
            )
        )
    return out


def _facial_metrics_from_payload(payload: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Map expression_metrics.json onto scoring-config facial_affect ids. No emotion labels."""
    out: list[dict[str, Any]] = []
    for metric_id, row in (payload.get("metrics") or {}).items():
        if metric_id not in config["categories"]["facial_affect"]["metrics"]:
            continue
        if not row or row.get("applicable") is False or row.get("value") is None:
            continue
        out.append(
            _metric_payload(
                metric_id=metric_id,
                category_id="facial_affect",
                raw_value=row["value"],
                confidence=float(row.get("confidence") or 0.5),
                config=config,
            )
        )
    return out


def _score_one(
    engine: Any,
    item: dict[str, Any],
    context: str,
    config: dict[str, Any],
    mode: str = "stage",
) -> dict[str, Any]:
    metric_def = config["categories"][item["category_id"]]["metrics"][item["id"]]
    score_context = context
    if "context_curves" in metric_def and context not in metric_def["context_curves"]:
        # Use an existing published curve (keynote, else first listed). Do not invent points.
        if "keynote" in metric_def["context_curves"]:
            score_context = "keynote"
        else:
            score_context = next(iter(metric_def["context_curves"]))
    scored = engine.score_metric(
        item["id"],
        item["raw_value"],
        item["confidence"],
        category_id=item["category_id"],
        context=score_context,
        mode=mode,
    )
    item["score"] = scored["score"]
    item["included"] = scored["included"]
    item["inclusion_factor"] = scored["inclusion_factor"]
    item["target_band"] = None
    item["details"] = {}
    return item


def _top_contributors(scored_metrics: list[dict[str, Any]]) -> list[str]:
    usable = [m for m in scored_metrics if m.get("score") is not None and m.get("included")]
    if not usable:
        return []
    mean = sum(float(m["score"]) for m in usable) / len(usable)
    ranked = sorted(
        usable,
        key=lambda m: abs(float(m["score"]) - mean) * float(m.get("weight") or 0),
        reverse=True,
    )
    return [m["id"] for m in ranked[:2]]


def _counterfactual(engine: Any, metrics: list[dict[str, Any]], category_id: str, context: str) -> Optional[str]:
    if not metrics:
        return None
    weakest = min(
        (m for m in metrics if m.get("score") is not None and m.get("included")),
        key=lambda m: float(m["score"]),
        default=None,
    )
    if weakest is None or not isinstance(weakest.get("raw_value"), (int, float)):
        return None
    current = float(weakest["raw_value"])
    trial = current * 0.7 if current > 0 else current
    try:
        before = weakest["score"]
        after = engine.score_metric(
            weakest["id"],
            trial,
            weakest["confidence"],
            category_id=category_id,
            context=context,
        )["score"]
    except Exception:
        return None
    if after is None or before is None:
        return None
    return (
        f"Changing {weakest['id']} from {current:.2f} toward {trial:.2f} "
        f"would move this category from about {int(round(before))} to about {int(round(after))}."
    )


def _evidence_from_inputs(
    transcript: dict[str, Any],
    metrics: list[dict[str, Any]],
    content: Optional[dict[str, Any]],
    output_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []

    def add(
        *,
        category_id: str,
        text: str,
        t_start: float,
        t_end: float,
        kind: str,
        modality: str,
        metric_id: Optional[str] = None,
        quote: Optional[str] = None,
        confidence: float = 0.8,
    ) -> None:
        evidence.append(
            {
                "id": f"ev-{len(evidence) + 1:04d}",
                "category_id": category_id,
                "metric_id": metric_id,
                "t_start": max(0.0, t_start),
                "t_end": max(t_start, t_end),
                "modality": modality,
                "kind": kind,
                "text": text[:400],
                "quote": quote,
                "seg_ids": [],
                "measurement": {"metric_id": metric_id, "value": None} if metric_id else None,
                "confidence": confidence,
                "user_disputed": False,
            }
        )

    disambig = (content or {}).get("fluency_disambig") if content else None
    added_disambig = 0
    for hit in (disambig or {}).get("disambiguations") or []:
        token = str(hit.get("word") or hit.get("token") or "")
        if not token:
            continue
        reading = "filler" if hit.get("is_filler") else "lexical"
        method = str(hit.get("method") or "heuristic")
        add(
            category_id="fluency",
            metric_id="fl_filler_words_per_min",
            text=f"{method} reading: '{token}' counted as {reading}.",
            quote=token[:400],
            t_start=float(hit.get("t_start") or 0),
            t_end=float(hit.get("t_end") or hit.get("t_start") or 0),
            kind="observation",
            modality="text",
            confidence=float(hit.get("confidence") or 0.5),
        )
        added_disambig += 1
        if added_disambig >= 12:
            break

    filler = next((m for m in metrics if m["id"] == "fl_filler_sounds_per_min" and m.get("raw_value")), None)
    if filler:
        add(
            category_id="fluency",
            metric_id="fl_filler_sounds_per_min",
            text=f"Measured filler-sound rate {float(filler['raw_value']):.2f} per minute.",
            t_start=0.0,
            t_end=min(5.0, float((transcript.get("duration") or 5))),
            kind="observation",
            modality="audio",
            confidence=float(filler.get("confidence") or 0.5),
        )
    wpm = next((m for m in metrics if m["id"] == "pp_wpm" and m.get("raw_value") is not None), None)
    if wpm:
        add(
            category_id="pace_pausing",
            metric_id="pp_wpm",
            text=f"Speaking rate {float(wpm['raw_value']):.1f} words per minute.",
            t_start=0.0,
            t_end=min(10.0, float((transcript.get("duration") or 10))),
            kind="observation",
            modality="audio",
            confidence=float(wpm.get("confidence") or 0.5),
        )
    message = (content or {}).get("message") or {}
    core = message.get("core_message")
    if isinstance(core, dict) and core.get("quote"):
        t = _seg_time(transcript, (core.get("seg_ids") or [None])[0]) or 0.0
        add(
            category_id="core_message",
            metric_id="cm_message_identifiable",
            text="Core message quote from the transcript.",
            quote=str(core["quote"])[:400],
            t_start=t,
            t_end=t + 4.0,
            kind="observation",
            modality="text",
        )
    if output_dir is not None:
        events_payload = _read_json(Path(output_dir) / "vision_events.json") or {}
        expr = _read_json(Path(output_dir) / "expression_metrics.json") or {}
        added_vision = 0
        for event in events_payload.get("events") or []:
            kind = event.get("type")
            if kind == "smile":
                add(
                    category_id="facial_affect",
                    metric_id="fa_smile_presence_ratio",
                    text="Smile signal (blendshape mouthSmile mean above the configured threshold).",
                    t_start=float(event.get("t_start") or 0),
                    t_end=float(event.get("t_end") or event.get("t_start") or 0),
                    kind="observation",
                    modality="video",
                    confidence=0.6,
                )
                added_vision += 1
            elif kind == "self_adaptor":
                add(
                    category_id="gestures_body",
                    metric_id="gb_self_adaptor_per_min",
                    text="Self-adaptor episode (wrist near the face/neck box).",
                    t_start=float(event.get("t_start") or 0),
                    t_end=float(event.get("t_end") or event.get("t_start") or 0),
                    kind="observation",
                    modality="video",
                    confidence=0.6,
                )
                added_vision += 1
            elif kind == "crossed_arms":
                add(
                    category_id="gestures_body",
                    metric_id="gb_closed_posture_ratio",
                    text="Closed-posture episode (wrists near opposite elbows).",
                    t_start=float(event.get("t_start") or 0),
                    t_end=float(event.get("t_end") or event.get("t_start") or 0),
                    kind="observation",
                    modality="video",
                    confidence=0.6,
                )
                added_vision += 1
            elif kind == "notes_down":
                add(
                    category_id="eye_contact",
                    metric_id="ec_reading_head_down_ratio",
                    text="Head-down episode (pitch below the notes-down threshold). Audience-facing time is a head-orientation proxy, not eye contact.",
                    t_start=float(event.get("t_start") or 0),
                    t_end=float(event.get("t_end") or event.get("t_start") or 0),
                    kind="observation",
                    modality="video",
                    confidence=0.6,
                )
                added_vision += 1
            if added_vision >= 8:
                break
        for obs in ((expr.get("metrics") or {}).get("fa_congruence") or {}).get("observations") or []:
            add(
                category_id="facial_affect",
                metric_id="fa_congruence",
                text=str(obs.get("note") or "Expression/content overlap flagged for review."),
                t_start=float(obs.get("t_start") or 0),
                t_end=float(obs.get("t_end") or 0),
                kind="observation",
                modality="video",
                confidence=0.4,
            )
    if not evidence:
        duration = float(transcript.get("duration") or 0)
        add(
            category_id="pace_pausing",
            text="Audio/text analysis ran; most categories lack enough evidence for a score.",
            t_start=0.0,
            t_end=max(0.1, duration),
            kind="observation",
            modality="audio",
            confidence=0.4,
        )
    return evidence


def _write_series(
    output_dir: Path,
    audio: Optional[dict[str, Any]],
    transcript: dict[str, Any],
    energy_points: Optional[list[dict[str, Any]]] = None,
) -> dict[str, str]:
    duration = int(math.ceil(float(transcript.get("duration") or audio.get("duration_s") if audio else 0) or 0))
    duration = max(duration, 1)
    empty = [{"t": float(i), "value": None} for i in range(duration)]
    series = {
        "pace": list(empty),
        "pitch": list(empty),
        "loudness": list(empty),
        "energy": list(empty),
    }
    for point in energy_points or []:
        t = int(float(point.get("t") or 0))
        value = point.get("value")
        if 0 <= t < duration and value is not None:
            series["energy"][t] = {"t": float(t), "value": float(value)}
    refs = {}
    for name, points in series.items():
        path = output_dir / f"series_{name}.json"
        path.write_text(json.dumps({"name": name, "resolution_s": 1, "points": points}, indent=2) + "\n")
        refs[name] = str(path)
    return refs


def run_fusion_scoring(
    *,
    session_id: str,
    output_dir: Path,
    context_type: str = "keynote",
    language: str = "en",
    slot_min: Optional[int] = None,
    qa_in_slot: bool = False,
    camera_setup: str = "unknown",
    ingest: Optional[dict[str, Any]] = None,
    transcript_path: Optional[Path] = None,
    audio_metrics_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    content_path: Optional[Path] = None,
    packages_dir: Optional[Path] = None,
    delivery_mode: str = "stage",
) -> dict[str, Any]:
    """Build analysis_result.json from existing stage artifacts only."""
    _ensure_scoring_path()
    from scoring import ScoringEngine, effective_weights

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packages = packages_dir or _packages_dir()
    engine = ScoringEngine(
        SCORING_CONFIG_VERSION,
        config_path=packages / "scoring-config",
    )
    config = engine.config
    if context_type not in config.get("weights", {}):
        context_type = "keynote"
    if delivery_mode not in (config.get("modes") or {"stage": {}}):
        delivery_mode = "stage"
    mode_weights = effective_weights(config, context_type, delivery_mode)

    transcript = _read_json(transcript_path) or _read_json(output_dir / "transcript.json") or {}
    if not transcript:
        for path in output_dir.glob("*_transcript.json"):
            transcript = json.loads(path.read_text())
            break
    audio = _read_json(audio_metrics_path) or _read_json(output_dir / "audio_metrics.json") or {}
    bundle = _read_json(metrics_path) or _read_json(output_dir / "metrics.json") or {"metrics": {}}
    content_raw = _read_json(content_path) or _read_json(output_dir / "content.json")
    content_unavailable = bool(content_raw and content_raw.get("unavailable"))
    content = None if content_unavailable else content_raw
    content_na_reason = (
        str((content_raw or {}).get("unavailable_reason") or "").strip() or None
        if content_unavailable
        else None
    )
    sidecar = _read_json(output_dir / "fluency_disambig.json")
    if sidecar and sidecar.get("disambiguations") and not content_unavailable:
        content = dict(content or {})
        existing = (content.get("fluency_disambig") or {}).get("disambiguations") or []
        if not existing:
            content["fluency_disambig"] = sidecar
    ingest = ingest or {}

    language = _normalize_language(language or transcript.get("language"))
    stats = _speech_stats(transcript)
    asr_c = float(bundle.get("asr_confidence") or stats["mean_word_prob"] or 0)
    prosody_c = float(bundle.get("prosody_confidence") or 0)
    music_flag = bool(audio.get("music_flag"))

    grouped = _metrics_from_bundle(bundle, config, music_flag)
    if content:
        for cid, items in _content_metrics(content, transcript, stats, asr_c, config).items():
            grouped[cid].extend(items)

    from pipeline.energy import compute_energy_metrics

    consents_early = _read_json(output_dir / "consents.json")
    expr_opt_in = bool(consents_early and decide_vision(consents_early).run_expression_metrics)
    energy_payload = compute_energy_metrics(
        audio=audio,
        gesture=_read_json(output_dir / "gesture_metrics.json"),
        expression=_read_json(output_dir / "expression_metrics.json"),
        content=content,
        transcript=transcript,
        pauses=_read_json(output_dir / "pauses.json"),
        duration_s=float(transcript.get("duration") or audio.get("duration_s") or 0),
        expression_opt_in=expr_opt_in,
    )
    if energy_payload:
        (output_dir / "energy_metrics.json").write_text(
            json.dumps(energy_payload, indent=2) + "\n", encoding="utf-8"
        )
    grouped["energy_presence"].extend(
        _energy_metrics_from_payload(energy_payload, config, prosody_c or asr_c)
    )

    extras = {
        "voiced_s": float(audio.get("voiced_s") or 0),
        "slot_min": slot_min,
        "qa_detected": bool((content or {}).get("qa", {}).get("pairs")),
        "question_count": len((content or {}).get("qa", {}).get("pairs") or []),
        "has_audio": bool(((ingest or {}).get("media_info") or {}).get("has_audio", True)),
        "screen_visible_s": float((ingest or {}).get("screen_visible_s") or 0),
        "screen_segments": int((ingest or {}).get("screen_segments") or 0),
        "camera_visible_s": float((ingest or {}).get("camera_visible_s") or 0),
    }
    flags = _read_json(output_dir / "analysis_flags.json") or {}
    audio_only_chosen = bool(flags.get("audio_only_chosen"))
    production_payload = _read_json(output_dir / "production_quality.json")
    if production_payload:
        grouped["production_quality"].extend(_production_metrics_from_payload(production_payload, config))
    layout_payload = _read_json(output_dir / "layout.json") or {}
    if layout_payload:
        extras["screen_visible_s"] = extras["screen_visible_s"] or float(
            (_layout_summary(output_dir) or {}).get("screen_visible_ratio") or 0
        ) * float(((ingest or {}).get("media_info") or {}).get("duration") or 0)

    scored_metrics: list[dict[str, Any]] = []
    categories_out: list[dict[str, Any]] = []
    for category_id in config["categories"]:
        weight = float(mode_weights.get(category_id, 0))
        na_reason = None
        applicable = True
        if delivery_mode == "stage" and category_id in ONLINE_STAGE_NA:
            applicable = False
            na_reason = ONLINE_STAGE_NA[category_id]
        elif delivery_mode != "stage" and category_id in ONLINE_NOT_IN_PHASE:
            applicable = False
            if audio_only_chosen and category_id in {"on_camera_presence", "screen_flow"}:
                na_reason = "You chose to analyse audio only."
            elif category_id == "on_camera_presence":
                consents = _read_json(output_dir / "consents.json")
                if consents and not decide_vision(consents).run_pose:
                    na_reason = "Video analysis is off. Turn it on in Settings to measure this."
                else:
                    na_reason = ONLINE_NOT_IN_PHASE[category_id]
            else:
                na_reason = ONLINE_NOT_IN_PHASE[category_id]
        elif category_id in VIDEO_CATEGORIES:
            consents = _read_json(output_dir / "consents.json")
            expr = _read_json(output_dir / "expression_metrics.json")
            audio_only = camera_setup == "audio_only" or bool(
                ((ingest or {}).get("modality") or {}).get("is_audio_only")
            )
            if category_id == "visual_aids":
                va = _read_json(output_dir / "visual_aids_metrics.json")
                slides = _read_json(output_dir / "slides.json")
                count = int((va or {}).get("slide_count") or (slides or {}).get("slide_count") or 0)
                extras["slides_detected"] = count
                if not va or count < 1:
                    applicable = False
                    na_reason = "No slides were detected and no deck was uploaded."
                else:
                    ok, reason = _min_evidence_ok(category_id, config, stats, extras)
                    if ok:
                        applicable = True
                        na_reason = None
                        grouped["visual_aids"].extend(_visual_aids_from_payload(va, config))
                    else:
                        applicable = False
                        na_reason = reason
            elif category_id == "gestures_body":
                from pipeline.accessibility import (
                    gesture_na_reason,
                    load_accessibility,
                    video_metrics_opted_out,
                )
                from pipeline.vision.gestures import attach_late_inputs

                profile = load_accessibility(output_dir)
                gesture = _read_json(output_dir / "gesture_metrics.json")
                failed = vision_failed_na_reason(output_dir, category_id)
                pose_allowed = bool(consents and decide_vision(consents).run_pose)
                if audio_only:
                    applicable = False
                    na_reason = "Audio-only media has no pose landmarks, so gestures & body is unavailable."
                elif video_metrics_opted_out(profile):
                    applicable = False
                    na_reason = gesture_na_reason(profile)
                elif failed and pose_allowed:
                    applicable = False
                    na_reason = failed
                elif pose_allowed and gesture:
                    gesture = attach_late_inputs(
                        gesture,
                        prominence_times_s=(audio or {}).get("emphasis_times_s"),
                        section_boundaries_s=_section_boundaries(content, transcript),
                        accessibility=profile,
                    )
                    extras["person_visible_ratio"] = float(gesture.get("person_visible_ratio") or 0.0)
                    extras["hands_visible_ratio"] = float(gesture.get("hands_visible_ratio") or 0.0)
                    ok, reason = _min_evidence_ok(category_id, config, stats, extras)
                    if ok:
                        applicable = True
                        na_reason = None
                        grouped["gestures_body"].extend(_body_metrics_from_payload(gesture, config))
                    else:
                        applicable = False
                        na_reason = reason
                else:
                    applicable = False
                    na_reason = (
                        video_category_na_reason(category_id, consents)
                        if consents
                        else VIDEO_CATEGORIES[category_id]
                    )
            elif category_id == "facial_affect":
                failed = vision_failed_na_reason(output_dir, category_id)
                expr_allowed = bool(consents and decide_vision(consents).run_expression_metrics)
                if failed and expr_allowed:
                    applicable = False
                    na_reason = failed
                elif expr_allowed and expr:
                    from pipeline.vision.expressiveness import attach_incongruence

                    events_payload = _read_json(output_dir / "vision_events.json") or {}
                    expr = attach_incongruence(
                        expr,
                        events_payload.get("events") or [],
                        transcript,
                        float(stats.get("duration_s") or 1.0),
                    )
                    extras["face_visible_ratio"] = float(expr.get("face_visible_ratio") or 0.0)
                    extras["face_px_median"] = float(expr.get("face_px_median") or 0.0)
                    ok, reason = _min_evidence_ok(category_id, config, stats, extras)
                    if ok:
                        applicable = True
                        na_reason = None
                        grouped["facial_affect"].extend(_facial_metrics_from_payload(expr, config))
                    else:
                        applicable = False
                        na_reason = reason
                else:
                    applicable = False
                    na_reason = (
                        video_category_na_reason(category_id, consents)
                        if consents
                        else VIDEO_CATEGORIES[category_id]
                    )
            elif category_id == "eye_contact":
                from pipeline.accessibility import (
                    gesture_na_reason,
                    load_accessibility,
                    video_metrics_opted_out,
                )

                profile = load_accessibility(output_dir)
                gaze = _read_json(output_dir / "gaze_metrics.json")
                failed = vision_failed_na_reason(output_dir, category_id)
                face_allowed = bool(consents and decide_vision(consents).run_face_landmarks)
                if audio_only:
                    applicable = False
                    na_reason = "Audio-only media has no face landmarks, so audience-facing time is unavailable."
                elif video_metrics_opted_out(profile):
                    applicable = False
                    na_reason = gesture_na_reason(profile)
                elif failed and face_allowed:
                    applicable = False
                    na_reason = failed
                elif face_allowed and gaze:
                    extras["face_visible_ratio"] = float(gaze.get("face_visible_ratio") or 0.0)
                    extras["face_px_median"] = float(gaze.get("face_px_median") or 0.0)
                    ok, reason = _min_evidence_ok(category_id, config, stats, extras)
                    if ok:
                        applicable = True
                        na_reason = None
                        grouped["eye_contact"].extend(_gaze_metrics_from_payload(gaze, config))
                    else:
                        applicable = False
                        na_reason = reason
                elif consents and decide_vision(consents).run_face_landmarks:
                    applicable = False
                    na_reason = (
                        "Audience-facing time needs a visible face; "
                        "screen recordings and missing faces stay N/A."
                    )
                else:
                    applicable = False
                    na_reason = (
                        video_category_na_reason(category_id, consents)
                        if consents
                        else VIDEO_CATEGORIES[category_id]
                    )
            else:
                applicable = False
                na_reason = (
                    video_category_na_reason(category_id, consents)
                    if consents
                    else VIDEO_CATEGORIES[category_id]
                )
        else:
            ok, reason = _min_evidence_ok(category_id, config, stats, extras)
            if not ok:
                applicable = False
                na_reason = reason
            if category_id in CONTENT_TEXT_CATEGORIES and not content:
                applicable = False
                na_reason = (
                    content_na_reason
                    or "Content analysis was not run, so this category has no inputs."
                )
            if category_id == "vocal_variety" and music_flag:
                applicable = False
                na_reason = "Background music makes vocal-variety scoring unavailable."
            if category_id == "qa" and not qa_in_slot:
                applicable = False
                na_reason = QA_NOT_IN_SLOT_REASON
            elif category_id == "qa" and not extras["qa_detected"]:
                applicable = False
                na_reason = "Q&A analysis has no detected question/answer pairs."
            if category_id == "energy_presence" and not grouped["energy_presence"]:
                applicable = False
                na_reason = (
                    "Energy & presence needs loudness, pitch-variation, gesture, "
                    "expressivity, or language inputs; missing modalities stay N/A."
                )

        raw_items = grouped.get(category_id, []) if applicable else []
        prepared = []
        for item in raw_items:
            try:
                prepared.append(_score_one(engine, dict(item), context_type, config, mode=delivery_mode))
            except Exception as exc:
                logger.info("Skipping metric %s: %s", item.get("id"), exc)

        if applicable and not prepared:
            applicable = False
            na_reason = na_reason or "Required inputs for this category were not produced."

        cat = None
        if applicable:
            cat = engine.score_category(category_id, prepared, context_type, mode=delivery_mode)
            if cat["score"] is None:
                # Metrics existed, but every one was below the inclusion floor
                # (confidence under 0.40) or had no usable weight.
                applicable = False
                floor = float((config.get("confidence") or {}).get("include_partial_from", 0.4))
                measured = [m for m in prepared if m.get("confidence") is not None]
                below = [m for m in measured if float(m["confidence"]) < floor]
                if measured and len(below) == len(measured):
                    na_reason = (
                        f"These signals were measured, but their confidence is below {floor:.2f}, "
                        "so this category stays N/A."
                    )
                else:
                    na_reason = na_reason or (
                        "These signals were measured, but none of them could be included in the score."
                    )
                cat = None

        if applicable and cat is not None:
            score = None if cat["score"] is None else int(round(cat["score"]))
            categories_out.append(
                {
                    "id": category_id,
                    "pillar": PILLAR_OF[category_id],
                    "applicable": True,
                    "na_reason": None,
                    "na_code": None,
                    "score": score,
                    "level": cat["level"],
                    "confidence": cat["confidence"],
                    "confidence_label": cat["confidence_label"],
                    "weight_used": weight,
                    "capped_by_gate": None,
                    "top_contributors": _top_contributors(prepared),
                    "evidence_ids": [],
                    "sources": _category_sources(config, category_id),
                    "counterfactual": _counterfactual(engine, prepared, category_id, context_type),
                }
            )
            for item in prepared:
                scored_metrics.append(
                    {
                        "id": item["id"],
                        "category_id": category_id,
                        "raw_value": item["raw_value"],
                        "unit": item["unit"],
                        "score": item.get("score"),
                        "weight": item.get("weight") or 0.0,
                        "confidence": item["confidence"],
                        "included": bool(item.get("included")),
                        "basis": item["basis"],
                        "target_band": None,
                        "details": {},
                    }
                )
        else:
            categories_out.append(
                {
                    "id": category_id,
                    "pillar": PILLAR_OF[category_id],
                    "applicable": False,
                    "na_reason": na_reason,
                    "na_code": _category_na_code(na_reason, category_id),
                    "score": None,
                    "level": None,
                    "confidence": None,
                    "confidence_label": None,
                    "weight_used": weight,
                    "capped_by_gate": None,
                    "top_contributors": [],
                    "evidence_ids": [],
                    "sources": _category_sources(config, category_id),
                    "counterfactual": None,
                }
            )

    overall = engine.score_overall(
        [
            {
                "id": c["id"],
                "score": c["score"],
                "confidence": c["confidence"] or 0.0,
                "applicable": c["applicable"],
            }
            for c in categories_out
        ],
        context_type,
        mode=delivery_mode,
    )
    if overall["score"] is not None:
        overall["score"] = int(round(overall["score"]))

    media_info = (ingest.get("media_info") or {}) if ingest else {}
    duration_s = float(media_info.get("duration") or stats["duration_s"] or audio.get("duration_s") or 0)
    has_video = bool((ingest.get("modality") or {}).get("has_video"))
    if ingest and "modality" not in ingest:
        has_video = not bool((ingest.get("modality") or {}).get("is_audio_only", True))
    if not ingest:
        has_video = False
    quality_payload = _read_json(output_dir / "vision_quality.json") or {}
    gesture_payload = _read_json(output_dir / "gesture_metrics.json") or {}
    gaze_payload = _read_json(output_dir / "gaze_metrics.json") or {}
    expr_payload = _read_json(output_dir / "expression_metrics.json") or {}
    camera_face_payload = _read_json(output_dir / "camera_face_quality.json") or {}

    evidence = _evidence_from_inputs(transcript, scored_metrics, content, output_dir=output_dir)
    by_cat: dict[str, list[str]] = {}
    for item in evidence:
        by_cat.setdefault(item["category_id"], []).append(item["id"])
    for category in categories_out:
        category["evidence_ids"] = by_cat.get(category["id"], [])[:4]

    pillars_cfg = config.get("pillars", {})
    pillars = []
    for pillar_id, cat_ids in pillars_cfg.items():
        members = [c for c in categories_out if c["id"] in cat_ids and c["applicable"] and c["score"] is not None]
        if members:
            wsum = sum(c["weight_used"] or 1 for c in members)
            score = int(round(sum((c["score"] or 0) * (c["weight_used"] or 1) for c in members) / wsum))
            conf = sum((c["confidence"] or 0) * (c["weight_used"] or 1) for c in members) / wsum
        else:
            score = None
            conf = None
        pillars.append(
            {
                "id": pillar_id,
                "score": score,
                "confidence": conf,
                "categories": list(cat_ids),
            }
        )

    series = _write_series(
        output_dir,
        audio,
        transcript,
        energy_points=(energy_payload or {}).get("energy_series"),
    )
    models = []
    if transcript.get("model") or transcript.get("asr_model"):
        models.append(
            {
                "component": "asr",
                "name": str(transcript.get("model") or transcript.get("asr_model")),
                "version": str(transcript.get("model") or transcript.get("asr_model")),
            }
        )
    models.append({"component": "scoring", "name": "scoring-config", "version": SCORING_CONFIG_VERSION})
    prompts = []
    if content and content.get("prompt_versions"):
        prompts = [{"id": k, "version": str(v)} for k, v in content["prompt_versions"].items()]

    warnings: list[str] = []
    if audio.get("noise_flag"):
        warnings.append("Background noise reduced measurement confidence.")
    if music_flag:
        warnings.append("Background music makes vocal-variety scoring unavailable.")
    if asr_c < 0.6:
        warnings.append("Transcription confidence is low; verify the transcript.")
    failed_warning = vision_failed_warning(output_dir)
    if failed_warning:
        warnings.append(failed_warning)

    result = {
        "schema_version": SCHEMA_VERSION,
        "session": {
            "id": _session_uuid(session_id),
            "context_type": context_type if context_type in config["weights"] else "keynote",
            "language": language,
            "slot_min": slot_min,
            "qa_in_slot": qa_in_slot,
            "camera_setup": camera_setup if camera_setup in {"stage", "to_camera", "screen_recording", "audio_only", "unknown", "composite"} else "unknown",
            "talk_plan_id": None,
            "delivery_mode": delivery_mode,
            "source_kind": "upload",
        },
        "provenance": {
            "pipeline_version": PIPELINE_VERSION,
            "scoring_config_version": SCORING_CONFIG_VERSION,
            "stages": [
                {"name": "fusion_scoring", "version": STAGE_VERSION, "duration_s": 0.0, "status": "ok"},
            ],
            "models": models,
            "prompts": prompts,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "media": {
            "duration_s": duration_s,
            "has_video": has_video,
            "has_audio": True,
            "speech_span_s": stats["speech_seconds"],
            "fps_analyzed": None,
        },
        "quality": {
            "asr_mean_word_prob": stats["mean_word_prob"],
            "snr_db": audio.get("snr_db"),
            "face_visible_ratio": _first_number(
                _ratio_from(camera_face_payload),
                _ratio_from(layout_payload),
                _ratio_from(quality_payload),
                _ratio_from(gaze_payload),
                _ratio_from(expr_payload),
            ),
            "person_visible_ratio": _first_number(
                _ratio_from(quality_payload, "person_visible_ratio"),
                _ratio_from(gesture_payload, "person_visible_ratio"),
            ),
            "hands_visible_ratio": _ratio_from(gesture_payload, "hands_visible_ratio"),
            "face_px_median": _first_number(
                gaze_payload.get("face_px_median") if gaze_payload else None,
                expr_payload.get("face_px_median") if expr_payload else None,
                quality_payload.get("mean_face_height_px") if quality_payload else None,
            ),
            "warnings": warnings,
        },
        "overall": {
            "score": overall["score"],
            "level": overall["level"],
            "coverage": overall["coverage"],
            "confidence": overall["confidence"],
            "display_band": overall["display_band"],
            "partial": overall["partial"],
        },
        "pillars": pillars,
        "categories": categories_out,
        "metrics": scored_metrics,
        "evidence": evidence,
        "insights": {
            "summary": "",
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
        },
        "series": series,
        "transcript_ref": str(transcript_path or output_dir / "transcript.json"),
        "core_delivery": _core_delivery(categories_out),
    }
    summary = _layout_summary(output_dir)
    if summary:
        result["layout_summary"] = summary

    schema = _load_schema(packages)
    import jsonschema

    jsonschema.validate(instance=result, schema=schema)
    dest = output_dir / "analysis_result.json"
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    from pipeline.body_slides import persist_body_slides
    from pipeline.timeline import persist_timeline

    persist_timeline(output_dir, duration_s=duration_s)
    persist_body_slides(output_dir, duration_s=duration_s)
    return result
