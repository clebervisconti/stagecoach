"""Structure options + outline (SPEC §9.4–§9.5 / issue #58)."""

from __future__ import annotations

from typing import Any

STRUCTURES: dict[str, dict[str, Any]] = {
    "scr": {
        "id": "scr",
        "name": "Situation–Complication–Resolution",
        "best_for": ["exec_briefing", "sales_pitch"],
        "sections": ["Situation", "Complication", "Answer first", "Support"],
    },
    "sparkline": {
        "id": "sparkline",
        "name": "Duarte Sparkline",
        "best_for": ["keynote"],
        "sections": ["What is", "What could be", "New bliss"],
    },
    "psb": {
        "id": "psb",
        "name": "Problem–Solution–Benefit",
        "best_for": ["sales_pitch", "breakout"],
        "sections": ["Problem", "Approach", "Sourced benefit", "Next step"],
    },
    "wsn": {
        "id": "wsn",
        "name": "What? / So What? / Now What?",
        "best_for": ["virtual_meeting", "other"],
        "sections": ["What", "So what", "Now what"],
    },
    "hero": {
        "id": "hero",
        "name": "Hero's journey, customer as hero",
        "best_for": ["keynote", "sales_pitch"],
        "sections": ["Before", "Obstacle", "Guide", "Transformation", "Lesson"],
    },
}

ALWAYS = (
    ("Opening", "Hook, stakes, and promise in the first 30–60 s; no bio or agenda first"),
    ("Key story", "One real story (character, conflict, resolution) tied to the message"),
    ("Close", "Restate the message, callback, CTA, plus a 30-second close after Q&A"),
)


def structures_for(context_type: str) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in STRUCTURES.values():
        if context_type in item["best_for"]:
            ranked.append(item)
    if context_type == "exec_briefing" and not any(row["id"] == "scr" for row in ranked):
        ranked.insert(0, STRUCTURES["scr"])
    if not ranked:
        ranked = [STRUCTURES["wsn"], STRUCTURES["psb"]]
    # Exec briefings always offer SCR as one of at most two options.
    if context_type == "exec_briefing":
        others = [row for row in ranked if row["id"] != "scr"]
        ranked = [STRUCTURES["scr"], *others]
    return ranked[:2]


def _outline_row(
    index: int,
    name: str,
    purpose: str,
    *,
    minutes: float,
    end: float,
    story: str,
    transition: str,
) -> dict[str, Any]:
    return {
        "n": index,
        "section": name,
        "purpose": purpose,
        "story_or_evidence": story,
        "transition": transition,
        "target_end": round(end, 2),
        "minutes": round(minutes, 2),
    }


def build_outline(
    plan: dict[str, Any],
    structure: dict[str, Any],
) -> list[dict[str, Any]]:
    slot = float(plan.get("slot_min") or 20)
    qa = float(plan.get("qa_min") or 0)
    speaking = max((slot - qa) * 0.90, 0.1)
    body_names: list[str] = list(structure["sections"])
    opening_min = speaking * 0.10
    close_min = speaking * 0.12
    body_total = speaking - opening_min - close_min
    per_body = body_total / max(len(body_names), 1)
    rows: list[dict[str, Any]] = []
    rows.append(
        _outline_row(
            1,
            ALWAYS[0][0],
            ALWAYS[0][1],
            minutes=opening_min,
            end=opening_min,
            story="Hook tied to the core message",
            transition="Pivot to the first body move",
        )
    )
    cursor = opening_min
    for index, name in enumerate(body_names):
        minutes = per_body
        cursor += minutes
        story = ALWAYS[1][1] if index == 0 else "Evidence for this point"
        rows.append(
            _outline_row(
                index + 2,
                name,
                f"{name}: advance the governing thought",
                minutes=minutes,
                end=cursor,
                story=story,
                transition="One-line bridge to the next section",
            )
        )
    rows.append(
        _outline_row(
            len(rows) + 1,
            ALWAYS[2][0],
            ALWAYS[2][1],
            minutes=close_min,
            end=cursor + close_min,
            story="Callback to the opening plus the CTA",
            transition="Hold for Q&A, then the 30-second close",
        )
    )
    names = {row["section"] for row in rows}
    assert "Opening" in names
    assert "Close" in names
    assert any("story" in row["story_or_evidence"].lower() for row in rows)
    return rows


def run_structure(plan: dict[str, Any]) -> dict[str, Any]:
    context = str(plan.get("context_type") or "other")
    options = structures_for(context)
    recommended = options[0]
    return {
        "prompt_id": "prep_structure_v1",
        "options": options,
        "recommended_id": recommended["id"],
        "outline": build_outline(plan, recommended),
    }
