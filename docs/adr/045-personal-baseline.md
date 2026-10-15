# ADR-045: Personal-baseline median/MAD and vs-your-baseline badge

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #66

## Context

SPEC §4.7.3: after ≥ 3 analyzed sessions in the same language, store per-metric median and MAD. The report shows the population-curve score **and** a badge `z = (x − median) / (1.4826 · MAD)`. Coaching prose that uses the baseline is v2. Scores must stay on population curves.

## Decision

- Implement compute + a serializable `BaselineSnapshot` in `packages/scoring/scoring/baseline.py`.
- No Alembic revision on this branch. A `personal_baselines` (or `users.personal_baselines` JSONB) write waits until #55's `008_talk_plans` is on `main` so two migrations do not fork.
- Same-language session count < 3 → no snapshot. MAD = 0 → badge is N/A.
- `keep_population_score` is a hard no-op so tests lock the "do not replace the score" rule.
- Badge UI on the report waits for a later PR that can touch report components without conflicting with unmerged siblings.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Add Alembic 008 here**  
   - ❌ #55 already uses 008 for talk_plans

2. **Replace the displayed score with z**  
   - ❌ Spec: scores stay on population curves

## Consequences

- Persist + report badge can import these functions after #55 merges.
