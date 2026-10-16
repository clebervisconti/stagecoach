# ADR-056: Goals API, progress, and dashed radar polygon

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #65

## Context

SPEC §7.3 / §7.5 / §8.2 / §8.8: users set goals such as "filler sounds < 3/min". `POST/GET /goals` persist `metric_id` XOR `category_id`, a comparator, a target, and `achieved_at`. The report radar draws a dashed polygon for category targets. The trends dashboard shows progress against the latest session.

## Decision

- Validation and progress live in `app/goals_service.py`. Exactly one of `metric_id` / `category_id`; comparators `< <= > >= =`.
- `GET /goals` reads the latest job's metric raw value or category score and sets `achieved_at` once when the target is met.
- Category targets (0–100) map onto radar pillars in `goalRadarPoints`. The dashed SVG uses `data-testid="goal-polygon"`.
- Trends create/list copy is local (en / pt-BR) so this branch does not edit `en.json` (owned by #61).
- `docs/DECISIONS.md`, `CHANGELOG.md`, and `.github/workflows/ci.yml` are not edited on this branch.

## Alternatives considered

1. **Require both metric and category**  
   - ❌ Spec: one key per row

2. **Reset achieved_at when the latest session misses**  
   - ❌ AC: stamp once

## Consequences

- Plan editor / export stay issue #61.
- No paid services. Progress is computed from stored scores, not a live LLM.
