"""prep_message_v1 + audience table (SPEC §9.2–§9.3 / issue #57).

Stand-in only in tests: no live LLM, no paid calls.
"""

from __future__ import annotations

import re
from typing import Any

MAX_CORE_WORDS = 15


def word_count(text: str) -> int:
    return len([part for part in (text or "").split() if part])


def enforce_core_message(text: str) -> str:
    words = [part for part in (text or "").split() if part]
    if len(words) <= MAX_CORE_WORDS:
        return " ".join(words)
    return " ".join(words[:MAX_CORE_WORDS])


def mark_unsourced_numbers(text: str, provided: str) -> str:
    """Mark digits the user did not provide with [needs source]."""
    provided_nums = set(re.findall(r"\d+(?:[.,]\d+)?", provided or ""))
    parts = re.split(r"(\d+(?:[.,]\d+)?)", text)
    out: list[str] = []
    for part in parts:
        if re.fullmatch(r"\d+(?:[.,]\d+)?", part) and part not in provided_nums:
            out.append(f"{part} [needs source]")
        else:
            out.append(part)
    return "".join(out)


def _claim_type(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\b(how|what|overview|about|introduction)\b", lowered) and not re.search(
        r"\b(should|must|will|need)\b", lowered
    ):
        return "topic"
    return "claim"


def three_tests(text: str) -> dict[str, str]:
    return {
        "so_what": "Does this matter to this audience now?",
        "could_disagree": "Could a reasonable person disagree? (claim, not a platitude)",
        "simple_concrete": "Is it simple and concrete (Heath)?",
        "text": text,
    }


def audience_adaptations(context_type: str) -> list[str]:
    if context_type == "exec_briefing":
        return [
            "Answer first",
            "1–3 summary slides plus an appendix",
            "Plan a discussion split",
        ]
    if context_type in {"breakout", "class_academic"}:
        return ["Lead with evidence and demos", "Keep one message"]
    if context_type == "keynote":
        return ["Lead with story and stakes", "Few memorable numbers"]
    if context_type == "sales_pitch":
        return ["Pain first", "One sourced benefit", "Clear next step"]
    return ["One message", "Evidence before ornament"]


def jargon_list(description: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z]{2,}[A-Za-z0-9_-]*\b", description or "")
    skip = {"Q", "A", "QA", "CTA", "AI", "OK"}
    return sorted({token for token in candidates if token not in skip})


def run_message(
    plan: dict[str, Any],
    *,
    generate: Any = None,
) -> dict[str, Any]:
    description = plan.get("description") or plan.get("title") or "This talk has a point"
    provided = " ".join(
        str(part)
        for part in (
            plan.get("description"),
            plan.get("goal"),
            plan.get("title"),
        )
        if part
    )
    if generate is not None:
        raw = generate({"plan": plan}) or {}
    else:
        title = plan.get("title") or "the recommendation"
        raw = {
            "candidates": [
                f"{title} is the decision this room must make",
                f"Approve the next step on {title}",
                f"{title} changes what this audience does next week",
            ],
            "cta": "Book the follow-up decision this week",
            "supporting": [
                "The current path costs more than the alternative",
                "One story shows the cost of waiting",
                "The ask is a dated next step",
            ],
        }
    candidates: list[dict[str, Any]] = []
    for text in (raw.get("candidates") or [])[:3]:
        clipped = enforce_core_message(str(text))
        assert word_count(clipped) <= MAX_CORE_WORDS
        candidates.append(
            {
                "text": clipped,
                "word_count": word_count(clipped),
                "claim_type": _claim_type(clipped),
                "tests": three_tests(clipped),
            }
        )
    while len(candidates) < 3:
        filler = enforce_core_message(f"{plan.get('title') or 'This talk'} needs a clear claim")
        candidates.append(
            {
                "text": filler,
                "word_count": word_count(filler),
                "claim_type": _claim_type(filler),
                "tests": three_tests(filler),
            }
        )
    supporting = [mark_unsourced_numbers(str(item), provided) for item in (raw.get("supporting") or [])]
    if len(supporting) < 2:
        supporting.extend(
            [
                "The status quo is more expensive than change",
                "A dated ask makes the CTA concrete",
            ][: 2 - len(supporting)]
        )
    supporting = supporting[:4]
    audience = dict(plan.get("audience") or {})
    table = {
        "who": audience.get("roles") or "not stated",
        "know_believe": audience.get("already_know") or "not stated",
        "what_is": audience.get("what_is") or "not stated",
        "what_could_be": audience.get("what_could_be") or "not stated",
        "objections": audience.get("objections") or "not stated",
        "decision": audience.get("decision") or "not stated",
        "stories": audience.get("stories") or "not stated",
        "format": plan.get("delivery_format") or "not stated",
    }
    return {
        "prompt_id": "prep_message_v1",
        "candidates": candidates[:3],
        "cta": raw.get("cta") or "Name a next step within a week",
        "supporting": supporting,
        "audience_table": table,
        "audience_adaptations": audience_adaptations(str(plan.get("context_type") or "other")),
        "jargon": jargon_list(description),
    }
