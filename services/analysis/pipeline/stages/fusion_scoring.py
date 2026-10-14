"""Fusion + scoring stage (issue #30, SPEC §6.8).

Maps existing metrics.json, audio features, transcript, and content_llm
outputs onto scoring-config v1.0.0. Missing inputs make a category N/A;
scores are never invented.
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

logger = logging.getLogger(__name__)

STAGE_VERSION = "1.0.0"
SCORING_CONFIG_VERSION = "1.0.0"
PIPELINE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

VIDEO_CATEGORIES = {
    "visual_aids": "Vision and slides stages were not run (Phase 1 is audio/text only).",
    "gestures_body": "Vision stage was not run; body metrics need a visible person.",
    "eye_contact": "Vision stage was not run; gaze metrics need a visible face.",
    "facial_affect": "Expression analysis is off and vision was not run.",
}

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
}

CLAIM_TYPE_LEVEL = {"none": 1, "topic": 2, "vague_claim": 3, "claim": 5}


def _ensure_scoring_path() -> None:
    candidates = [
        Path("/packages/scoring"),
        Path(__file__).resolve().parents[4] / "packages" / "scoring",
    ]
    for path in candidates:
        if (path / "scoring").exists() or (path / "scoring" / "engine.py").exists() or (path / "pyproject.toml").exists():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            return


def _packages_dir() -> Path:
    candidates = (
        Path("/packages"),
        Path(__file__).resolve().parents[4] / "packages",
    )
    for path in candidates:
        if (path / "scoring-config").exists() or (path / "schemas").exists():
            return path
    return Path(__file__).resolve().parents[4] / "packages"


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
    return json.loads(path.read_text())


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
        if key in {"slides_detected", "person_visible_ratio", "hands_visible_ratio", "face_visible_ratio", "face_px_median"}:
            return False, "Required video evidence is not available."
    return True, None


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


def _llm_confidence(block: dict[str, Any], asr_c: float) -> float:
    meta = block.get("consistency_metadata") or {}
    agreements = [float(v.get("agreement", 0)) for v in meta.values() if isinstance(v, dict)]
    agreement = sum(agreements) / len(agreements) if agreements else 0.7
    verify = block.get("verification_metadata") or {}
    factors = [float(v.get("confidence_factor", 1)) for v in verify.values() if isinstance(v, dict)]
    validity = sum(factors) / len(factors) if factors else 1.0
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

    def add(category: str, metric_id: str, raw: Any, block: dict[str, Any]) -> None:
        if raw is None:
            return
        out[category].append(
            _metric_payload(
                metric_id=metric_id,
                category_id=category,
                raw_value=raw,
                confidence=_llm_confidence(block, asr_c),
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
            add("clarity", "cl_claims_supported_ratio", supported / len(claims), audience)
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
        if not (metric_def.get("llm_level") or "curve" in metric_def or "context_curves" in metric_def or "mapping" in metric_def):
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
    """Audio-only energy metrics from existing audio_metrics. No emotion terms."""
    metrics: list[dict[str, Any]] = []
    too_soft = audio.get("too_soft_ratio")
    if too_soft is None and audio.get("intensity_sd_db_median") is not None:
        # Not the same measurement — do not invent ep_too_soft_ratio.
        too_soft = None
    if isinstance(too_soft, (int, float)):
        metrics.append(
            _metric_payload(
                metric_id="ep_too_soft_ratio",
                category_id="energy_presence",
                raw_value=float(too_soft),
                confidence=confidence,
                config=config,
            )
        )
    trajectory = audio.get("energy_trajectory")
    if isinstance(trajectory, (int, float)):
        metrics.append(
            _metric_payload(
                metric_id="ep_energy_trajectory",
                category_id="energy_presence",
                raw_value=float(trajectory),
                confidence=confidence,
                config=config,
            )
        )
    return metrics


def _score_one(
    engine: Any,
    item: dict[str, Any],
    context: str,
    config: dict[str, Any],
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


def _write_series(output_dir: Path, audio: Optional[dict[str, Any]], transcript: dict[str, Any]) -> dict[str, str]:
    duration = int(math.ceil(float(transcript.get("duration") or audio.get("duration_s") if audio else 0) or 0))
    duration = max(duration, 1)
    empty = [{"t": float(i), "value": None} for i in range(duration)]
    series = {
        "pace": list(empty),
        "pitch": list(empty),
        "loudness": list(empty),
        "energy": list(empty),
    }
    windows = (audio or {}).get("pvq_windows") or []
    for window in windows:
        start = int(float(window.get("start") or 0))
        value = window.get("value")
        if 0 <= start < duration and value is not None:
            series["energy"][start] = {"t": float(start), "value": float(value)}
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
) -> dict[str, Any]:
    """Build analysis_result.json from existing stage artifacts only."""
    _ensure_scoring_path()
    from scoring import ScoringEngine

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

    transcript = _read_json(transcript_path) or _read_json(output_dir / "transcript.json") or {}
    if not transcript:
        for path in output_dir.glob("*_transcript.json"):
            transcript = json.loads(path.read_text())
            break
    audio = _read_json(audio_metrics_path) or _read_json(output_dir / "audio_metrics.json") or {}
    bundle = _read_json(metrics_path) or _read_json(output_dir / "metrics.json") or {"metrics": {}}
    content = _read_json(content_path) or _read_json(output_dir / "content.json")
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
    grouped["energy_presence"].extend(_energy_from_audio(audio, config, prosody_c or asr_c))

    extras = {
        "voiced_s": float(audio.get("voiced_s") or 0),
        "slot_min": slot_min,
        "qa_detected": bool((content or {}).get("qa", {}).get("pairs")),
        "question_count": len((content or {}).get("qa", {}).get("pairs") or []),
    }

    scored_metrics: list[dict[str, Any]] = []
    categories_out: list[dict[str, Any]] = []
    for category_id in config["categories"]:
        weight = float(config["weights"].get(context_type, {}).get(category_id, 0))
        na_reason = None
        applicable = True
        if category_id in VIDEO_CATEGORIES:
            applicable = False
            na_reason = VIDEO_CATEGORIES[category_id]
        else:
            ok, reason = _min_evidence_ok(category_id, config, stats, extras)
            if not ok:
                applicable = False
                na_reason = reason
            if category_id in {
                "core_message",
                "structure",
                "storytelling",
                "audience_adaptation",
                "opening_close",
                "clarity",
                "impact",
            } and not content:
                applicable = False
                na_reason = "Content analysis was not run, so this category has no inputs."
            if category_id == "vocal_variety" and music_flag:
                applicable = False
                na_reason = "Background music makes vocal-variety scoring unavailable."
            if category_id == "qa" and not extras["qa_detected"]:
                applicable = False
                na_reason = "Q&A analysis has no detected question/answer pairs."
            if category_id == "energy_presence" and not grouped["energy_presence"] and not content:
                applicable = False
                na_reason = "Energy & presence needs audio intensity trajectory or content-language inputs that are not available."

        raw_items = grouped.get(category_id, []) if applicable else []
        prepared = []
        for item in raw_items:
            try:
                prepared.append(_score_one(engine, dict(item), context_type, config))
            except Exception as exc:
                logger.info("Skipping metric %s: %s", item.get("id"), exc)

        if applicable and not prepared:
            applicable = False
            na_reason = na_reason or "Required inputs for this category were not produced."

        if applicable:
            cat = engine.score_category(category_id, prepared, context_type)
            score = None if cat["score"] is None else int(round(cat["score"]))
            categories_out.append(
                {
                    "id": category_id,
                    "pillar": PILLAR_OF[category_id],
                    "applicable": True,
                    "na_reason": None,
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

    evidence = _evidence_from_inputs(transcript, scored_metrics, content)
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

    series = _write_series(output_dir, audio, transcript)
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

    result = {
        "schema_version": SCHEMA_VERSION,
        "session": {
            "id": _session_uuid(session_id),
            "context_type": context_type if context_type in config["weights"] else "keynote",
            "language": language,
            "slot_min": slot_min,
            "qa_in_slot": qa_in_slot,
            "camera_setup": camera_setup if camera_setup in {"stage", "to_camera", "screen_recording", "audio_only", "unknown"} else "unknown",
            "talk_plan_id": None,
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
            "face_visible_ratio": None,
            "person_visible_ratio": None,
            "hands_visible_ratio": None,
            "face_px_median": None,
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
    }

    schema = _load_schema(packages)
    import jsonschema

    jsonschema.validate(instance=result, schema=schema)
    dest = output_dir / "analysis_result.json"
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result
