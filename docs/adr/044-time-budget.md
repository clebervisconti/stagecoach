# ADR-044: Deterministic time budget, cut list, and rehearsal plan

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #59

## Context

SPEC §9.6 and the Phase 3 AC require `available_speaking_min = (slot − Q&A − buffer) × 0.90`, a section split, `max_script_words`, a five-step cut list that never cuts the hook / key story / close, and a dated rehearsal plan counted backwards from the talk date. Arithmetic is code, not LLM.

## Decision

- Put the math in `packages/scoring/scoring/time_budget.py` with unit tests.
- Default `WPM_plan` is the user's measured median when present, otherwise 130.
- Body is 2–4 points; opening 10%; close 12% (mid of 10–15%).
- Cut order: off-message → extra example → background → detailed data → collapsible. `must_include` and hook/story/close are `protect`.
- Rehearsal steps are dated from the talk date; keynotes get an extra run-through.
- Wiring into `prep_llm` / plan outputs waits for #55 (plan API) to merge. This PR does not touch API or Alembic.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Ask the LLM for the minute split**  
   - ❌ Spec: arithmetic is code

2. **Ship the plan-output JSON in this PR**  
   - ❌ That writes `talk_plans.outputs` and conflicts with #55

## Consequences

- #58/#61 can import these functions after #55 lands.
