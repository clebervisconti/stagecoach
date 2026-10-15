"""Deterministic time budget, cut list, and rehearsal plan (SPEC §9.6 / issue #59)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

SPEAKING_RATIO = 0.90
DEFAULT_WPM = 130.0
OPENING_FRAC = 0.10
CLOSE_FRAC = 0.12  # mid of the 10–15% close band
ADLIB_FRAC = 0.10
PROTECTED_KINDS = frozenset({"hook", "key_story", "close"})
CUT_ORDER: tuple[str, ...] = (
    "off_message",
    "extra_example",
    "background",
    "detailed_data",
    "collapsible",
)


@dataclass(frozen=True)
class SectionBudget:
    name: str
    minutes: float
    cumulative_end: float


@dataclass(frozen=True)
class TimeBudget:
    slot_min: float
    qa_min: float
    changeover_buffer_min: float
    available_speaking_min: float
    wpm_plan: float
    max_script_words: float
    target_script_words: float
    sections: list[SectionBudget]


@dataclass(frozen=True)
class CutItem:
    id: str
    kind: str
    text: str
    must_include: bool = False


@dataclass(frozen=True)
class CutAction:
    id: str
    kind: str
    step: int
    action: Literal["cut", "protect"]


@dataclass(frozen=True)
class RehearsalStep:
    day_offset: int
    date: date | None
    title: str
    links_to_recording: bool


def available_speaking_min(
    slot_min: float,
    qa_min: float = 0.0,
    changeover_buffer_min: float = 0.0,
) -> float:
    remaining = slot_min - qa_min - changeover_buffer_min
    if remaining <= 0:
        raise ValueError("slot minus Q&A and buffer must be positive")
    return remaining * SPEAKING_RATIO


def wpm_plan(measured_median: float | None) -> float:
    if measured_median is not None and measured_median > 0:
        return float(measured_median)
    return DEFAULT_WPM


def max_script_words(speaking_min: float, wpm: float) -> float:
    return speaking_min * wpm


def section_split(speaking_min: float, body_points: int = 3) -> list[SectionBudget]:
    points = min(4, max(2, body_points))
    opening = speaking_min * OPENING_FRAC
    close = speaking_min * CLOSE_FRAC
    body_total = speaking_min - opening - close
    per_point = body_total / points
    sections: list[SectionBudget] = []
    cursor = 0.0
    pieces: list[tuple[str, float]] = [("Opening", opening)]
    for index in range(points):
        pieces.append((f"Body {index + 1}", per_point))
    pieces.append(("Close", close))
    for name, minutes in pieces:
        cursor += minutes
        sections.append(SectionBudget(name=name, minutes=minutes, cumulative_end=cursor))
    return sections


def build_time_budget(
    *,
    slot_min: float,
    qa_min: float = 0.0,
    changeover_buffer_min: float = 0.0,
    measured_median_wpm: float | None = None,
    body_points: int = 3,
) -> TimeBudget:
    speaking = available_speaking_min(slot_min, qa_min, changeover_buffer_min)
    pace = wpm_plan(measured_median_wpm)
    ceiling = max_script_words(speaking, pace)
    return TimeBudget(
        slot_min=slot_min,
        qa_min=qa_min,
        changeover_buffer_min=changeover_buffer_min,
        available_speaking_min=speaking,
        wpm_plan=pace,
        max_script_words=ceiling,
        target_script_words=ceiling * (1.0 - ADLIB_FRAC),
        sections=section_split(speaking, body_points),
    )


def build_cut_list(items: list[CutItem]) -> list[CutAction]:
    """Apply the five-step cut order. Never cut hook / key story / close / must-include."""
    actions: list[CutAction] = []
    for step, kind in enumerate(CUT_ORDER, start=1):
        for item in items:
            protected = item.must_include or item.kind in PROTECTED_KINDS
            if item.kind == kind:
                actions.append(
                    CutAction(
                        id=item.id,
                        kind=item.kind,
                        step=step,
                        action="protect" if protected else "cut",
                    )
                )
            elif protected and kind == CUT_ORDER[0] and item.kind in PROTECTED_KINDS:
                # Record protections once, on the first pass, if they are not a cut kind.
                if not any(existing.id == item.id for existing in actions):
                    actions.append(CutAction(id=item.id, kind=item.kind, step=0, action="protect"))
    for item in items:
        if (item.must_include or item.kind in PROTECTED_KINDS) and not any(
            existing.id == item.id for existing in actions
        ):
            actions.append(CutAction(id=item.id, kind=item.kind, step=0, action="protect"))
    return actions


def rehearsal_plan(
    talk_on: date | None,
    *,
    context_type: str = "exec_briefing",
    today: date | None = None,
) -> list[RehearsalStep]:
    """Dated schedule counted backwards from the talk date."""
    keynote = context_type == "keynote"
    offsets_and_titles: list[tuple[int, str, bool]] = [
        (14 if keynote else 10, "Lock outline and core message", False),
        (10 if keynote else 7, "Full timed run-through standing, out loud", True),
        (7 if keynote else 4, "Second full timed run-through; record one pass", True),
        (3, "Third timed run-through; memorize first 60 s and the close", True),
        (1, "Q&A: 5–8 likely questions, answer-first 30–90 s", False),
        (0, "Talk day: timer signals and 30-second close after Q&A", False),
    ]
    if keynote:
        offsets_and_titles.insert(3, (5, "Extra keynote run-through (Gallo-style reps)", True))
    steps: list[RehearsalStep] = []
    for offset, title, record in offsets_and_titles:
        when = talk_on - timedelta(days=offset) if talk_on is not None else None
        if today is not None and when is not None and when < today:
            continue
        steps.append(
            RehearsalStep(
                day_offset=offset,
                date=when,
                title=title,
                links_to_recording=record,
            )
        )
    return steps
