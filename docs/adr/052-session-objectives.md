# ADR-052: Session–plan link, tm_section_variance, rehearsal progress

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #63

## Context

SPEC §9.7 / §8.8 / §4.4.16: a rehearsal session can link to a talk plan. `tm_section_variance` is the mean absolute % deviation of actual vs planned section durations. The plan view shows progress across ≥ 2 rehearsals. The report Time tab is a planned-vs-actual table.

## Decision

- Arithmetic lives in `packages/scoring/scoring/section_variance.py` (not re-exported from `__init__.py`).
- `POST /sessions` accepts optional `talk_plan_id`. Ownership is 404 via `require_owned` (same as plans).
- Report Objectives panel and Time tab UI wait so this PR does not edit the shared report page / i18n files (those belong to the trends dashboard PR).
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Add the Objectives panel on the report in this PR**  
   - ❌ Edits `sessions/[id]/page.tsx` and i18n, which the trends PR also needs

2. **Allow linking another user's plan**  
   - ❌ Existence leak; spec is ownership-404

## Consequences

- After trends merge, a follow-up can render `rehearsal_progress` and `planned_vs_actual` on the report.
