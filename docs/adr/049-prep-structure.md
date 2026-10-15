# ADR-049: Structure options and outline

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #58

## Context

SPEC §9.4–§9.5: offer 1–2 structures that fit the context (SCR, Sparkline, PSB, WSN, hero's journey). Executive briefings must include SCR. Every outline always adds opening, at least one real story, and a close. Rows are section / purpose / story or evidence / transition / target end / minutes.

## Decision

- Implement the catalog and outline builder in `services/analysis/pipeline/prep_structure.py`.
- Use a local 90% speaking split so the worker image does not import `packages/scoring` (that package is not in the worker CI image).
- Do not write plan outputs or touch the web form / plan API on this branch.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Import `scoring.time_budget` for the minute split**  
   - ❌ Worker tests / image do not install the scoring package

2. **Offer more than two structures**  
   - ❌ Spec: 1–2 per context

## Consequences

- After #56 merges, `prep_llm` can store `run_structure(plan)` under `outputs.structure`.
