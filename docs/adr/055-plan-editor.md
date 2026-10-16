# ADR-055: Plan editor, readiness scores, and export

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #61

## Context

SPEC §9.8: the prep outputs view mirrors the talk-prep format. Every section is editable inline and regenerable with feedback. Readiness covers rubric categories 1–8 and 16–17 from materials; 9–15 stay N/A until a rehearsal. The plan exports to PDF and Markdown. Top 3 changes come first.

## Decision

- `/prep/{id}` is the editor. Save uses existing `PATCH /plans`; regenerate uses `POST /plans/{id}/regenerate`.
- Readiness and top-3 are deterministic in `apps/web/lib/plan-readiness.ts` (no live LLM).
- Markdown is generated client-side. PDF is the print page (`window.print`), same pattern as the session print view.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Score readiness with a live LLM**  
   - ❌ Paid / flaky; materials presence is enough to lock 1–8 / 16–17 vs 9–15

2. **Add a new export API**  
   - ❌ Would edit `main.py` and conflict with the goals PR

## Consequences

- Goals (#65) stay off this branch (radar / `/goals`).
