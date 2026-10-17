"""Talk-prep job: deterministic generators, optional local model for the core message."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (TypeError, ValueError):
        return False


def placeholder_outputs(section: str, feedback: str) -> dict[str, Any]:
    """Stand-in outputs so the plan is readable before LLM issues land."""
    return {
        "status": "placeholder",
        "section": section,
        "feedback_chars": len(feedback or ""),
        "note": "prep_* LLM calls land in issues #56–#62; this job only marks the plan ready.",
        "core_message": None,
        "structure": None,
        "outline": None,
        "slide_review": None,
        "time_budget": None,
        "cut_list": None,
        "rehearsal_plan": None,
        "objectives": [],
    }


def apply_prep_placeholder(
    plan_id: str,
    *,
    section: str = "all",
    feedback: str = "",
    llm_settings: Optional[dict[str, Any]] = None,
    database_url: Optional[str] = None,
) -> dict[str, Any]:
    settings = dict(llm_settings or {})
    for banned in ("api_key", "key", "secret", "token"):
        settings.pop(banned, None)
    outputs = placeholder_outputs(section, feedback)
    payload = {
        "plan_id": plan_id,
        "section": section,
        "status": "ready",
        "outputs": outputs,
        "llm_settings": settings,
    }
    url = database_url or os.getenv("DATABASE_URL")
    if not url or not _is_uuid(plan_id):
        logger.info("Skipping talk_plans persist for plan %s", plan_id)
        return payload

    engine = create_engine(url)
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE talk_plans
                SET status = 'ready',
                    outputs = CAST(:outputs AS JSONB),
                    updated_at = :now
                WHERE id = CAST(:plan_id AS UUID)
                """
            ),
            {"outputs": json.dumps(outputs), "now": now, "plan_id": plan_id},
        )
    return payload


def _scoring_path() -> None:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "packages" / "scoring"
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            return
    mounted = Path("/packages/scoring")
    if mounted.exists() and str(mounted) not in sys.path:
        sys.path.insert(0, str(mounted))


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text_value = str(value)[:10]
    try:
        return date.fromisoformat(text_value)
    except ValueError:
        return None


def _message_block(plan: dict[str, Any], generate: Callable[..., Any] | None) -> dict[str, Any]:
    from pipeline.prep_message import run_message

    if generate is None:
        body = run_message(plan)
        body["source"] = "deterministic"
        return body
    try:
        body = run_message(plan, generate=generate)
        body["source"] = "model"
        return body
    except Exception:
        logger.info("prep message model unavailable; using deterministic candidates")
        body = run_message(plan)
        body["source"] = "deterministic"
        body["model_note"] = (
            "The language model was unavailable, so candidates use the deterministic claim."
        )
        return body


def _live_generate(plan: dict[str, Any], feedback: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def generate(_payload: dict[str, Any]) -> dict[str, Any]:
        from llm import LLMClient

        client = LLMClient(use_cassettes=False)
        client.provider.timeout = 8
        client.provider.retry_config = {"max_attempts": 1, "backoff_factor": 1}
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["candidates", "cta", "supporting"],
            "properties": {
                "candidates": {"type": "array", "items": {"type": "string"}},
                "cta": {"type": "string"},
                "supporting": {"type": "array", "items": {"type": "string"}},
            },
        }
        response = client.generate_structured(
            prompt_id="prep_message_v1",
            inputs={
                "title": plan.get("title"),
                "description": plan.get("description"),
                "context_type": plan.get("context_type"),
                "slot_min": plan.get("slot_min"),
                "audience": plan.get("audience"),
                "feedback": feedback,
            },
            schema=schema,
            temperature=0.4,
        )
        return dict(response.data)

    return generate


def build_plan_outputs(
    plan: dict[str, Any],
    *,
    section: str = "all",
    feedback: str = "",
    generate: Callable[..., Any] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill prep sections from the existing generators. No fabricated scores."""
    from pipeline.prep_slides import review_deck
    from pipeline.prep_structure import run_structure

    _scoring_path()
    from scoring.time_budget import CutItem, build_cut_list, build_time_budget, rehearsal_plan

    message = _message_block(plan, generate)
    structure = run_structure(plan)
    slot = float(plan.get("slot_min") or 20)
    qa_min = float(plan.get("qa_min") or 0)
    budget = build_time_budget(slot_min=slot, qa_min=qa_min)
    cuts = build_cut_list(
        [
            CutItem("hook", "hook", "Opening hook"),
            CutItem("story", "key_story", "Key story"),
            CutItem("close", "close", "Close and CTA"),
            CutItem("off", "off_message", "Material that does not serve the core message"),
            CutItem("extra", "extra_example", "A second example that repeats the first"),
            CutItem("bg", "background", "Background the audience already knows"),
            CutItem("data", "detailed_data", "A full table the audience cannot read"),
            CutItem("flex", "collapsible", "A section you can skip if time runs short"),
        ]
    )
    talk_on = _as_date(plan.get("talk_date"))
    steps = rehearsal_plan(talk_on, context_type=str(plan.get("context_type") or "other"))
    deck_path = plan.get("deck_path")
    slides = review_deck(Path(deck_path) if deck_path else None)
    if not slides.get("table"):
        slides = {**slides, "note": "No deck uploaded, so the slide table is empty."}
    core = message["candidates"][0]
    outputs: dict[str, Any] = {
        "status": "ready",
        "section": section,
        "feedback_chars": len(feedback or ""),
        "core_message": message,
        "audience": message.get("audience_table"),
        "structure": structure,
        "outline": structure.get("outline"),
        "slide_review": slides,
        "time_budget": {
            "slot_min": budget.slot_min,
            "qa_min": budget.qa_min,
            "available_speaking_min": budget.available_speaking_min,
            "wpm_plan": budget.wpm_plan,
            "max_script_words": budget.max_script_words,
            "target_script_words": budget.target_script_words,
            "sections": [
                {"name": row.name, "minutes": row.minutes, "cumulative_end": row.cumulative_end}
                for row in budget.sections
            ],
            "note": "Speaking time targets 90% of the slot after Q&A.",
        },
        "cut_list": [
            {"id": row.id, "kind": row.kind, "step": row.step, "action": row.action}
            for row in cuts
        ],
        "rehearsal_plan": {
            "talk_date": talk_on.isoformat() if talk_on else None,
            "steps": [
                {
                    "day_offset": step.day_offset,
                    "date": step.date.isoformat() if step.date else None,
                    "title": step.title,
                    "links_to_recording": step.links_to_recording,
                }
                for step in steps
            ],
        },
        "objectives": [
            {
                "id": "core_message",
                "text": core["text"],
                "check_type": "llm_presence",
                "word_count": core["word_count"],
            },
            {"id": "cta", "text": message.get("cta"), "check_type": "llm_presence"},
            {
                "id": "time_90",
                "text": "Speaking time stays within 90% of the slot",
                "check_type": "metric_threshold",
                "target_min": budget.available_speaking_min,
            },
        ],
    }
    if section not in {"", "all"}:
        merged = dict(previous or {})
        if section in outputs:
            merged[section] = outputs[section]
            if section == "structure":
                merged["outline"] = outputs["outline"]
            if section == "core_message":
                merged["audience"] = outputs["audience"]
                merged["objectives"] = outputs["objectives"]
        merged["status"] = "ready"
        merged["section"] = section
        merged["feedback_chars"] = len(feedback or "")
        if feedback:
            merged["feedback_note"] = "Feedback is stored with the regeneration; it is not a score."
        return merged
    if feedback:
        outputs["feedback_note"] = "Feedback is stored with the regeneration; it is not a score."
    return outputs


def _load_plan(url: str, plan_id: str) -> dict[str, Any] | None:
    engine = create_engine(url)
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    """
                    SELECT title, context_type, description, audience, goal, slot_min,
                           qa_in_slot, qa_min, language, delivery_format, talk_date,
                           must_include, outputs
                    FROM talk_plans
                    WHERE id = CAST(:plan_id AS UUID)
                    """
                ),
                {"plan_id": plan_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    data = dict(row)
    if data.get("talk_date") is not None and not isinstance(data["talk_date"], str):
        data["talk_date"] = data["talk_date"].isoformat()
    return data


def _persist_outputs(url: str, plan_id: str, outputs: dict[str, Any]) -> None:
    engine = create_engine(url)
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE talk_plans
                SET status = 'ready',
                    outputs = CAST(:outputs AS JSONB),
                    updated_at = :now
                WHERE id = CAST(:plan_id AS UUID)
                """
            ),
            {"outputs": json.dumps(outputs), "now": now, "plan_id": plan_id},
        )


def apply_prep_plan(
    plan_id: str,
    *,
    section: str = "all",
    feedback: str = "",
    llm_settings: Optional[dict[str, Any]] = None,
    database_url: Optional[str] = None,
    plan: Optional[dict[str, Any]] = None,
    use_llm: bool = False,
) -> dict[str, Any]:
    """Build a real plan and persist it when the row exists."""
    settings = dict(llm_settings or {})
    for banned in ("api_key", "key", "secret", "token"):
        settings.pop(banned, None)
    url = database_url or os.getenv("DATABASE_URL")
    stored = _load_plan(url, plan_id) if url and _is_uuid(plan_id) else None
    source = dict(stored or {})
    if plan:
        source.update(plan)
    if not source:
        source = {"title": "Untitled talk", "context_type": "other", "slot_min": 20}
    previous = source.get("outputs") if isinstance(source.get("outputs"), dict) else None
    generate = _live_generate(source, feedback) if use_llm else None
    outputs = build_plan_outputs(
        source,
        section=section,
        feedback=feedback,
        generate=generate,
        previous=previous,
    )
    payload = {
        "plan_id": plan_id,
        "section": section,
        "status": "ready",
        "outputs": outputs,
        "llm_settings": settings,
    }
    if not url or not _is_uuid(plan_id):
        logger.info("Skipping talk_plans persist for plan %s", plan_id)
        return payload
    _persist_outputs(url, plan_id, outputs)
    return payload
