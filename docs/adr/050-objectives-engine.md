# ADR-050: prep_objectives_v1 and the objective check engine

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #62

## Context

SPEC §9.7: measurable objectives with check types `llm_semantic_match` (+ timing / window), `llm_presence`, `outline_alignment` (Needleman–Wunsch), and `metric_threshold` (including per slide). Status is `met` / `partial` / `not_met` / `na` with evidence. The objectives score counts partial as 0.5.

## Decision

- Put the engine in `packages/scoring/scoring/objectives.py`. Do **not** re-export it from `scoring/__init__.py` (avoids a sibling conflict with #59's time-budget exports).
- Alignment and thresholds are code. LLM check types accept a provided match in `[0, 1]` so tests never call a paid model.
- `prep_objectives` is a stand-in that emits the default §9.7 checks from a plan dict.
- Do not write `objective_scores` rows or touch the plan API on this branch.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Call the live LLM from unit tests**  
   - ❌ Paid / flaky; stand-in match scores are enough to lock bands

2. **Export from `scoring/__init__.py` now**  
   - ❌ That file is already owned by the merged time-budget PR; later wiring can add the export

## Consequences

- A later PR can persist `evaluate_check` results into `objective_scores` after #55/#56 are on main.
