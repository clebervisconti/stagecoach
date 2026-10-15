# ADR-043: talk_plans, goals, objective_scores, and the plan API

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #55

## Context

SPEC §7.3, §7.5, and §9 require `talk_plans`, `goals`, and `objective_scores`, plus `POST/GET/PATCH /plans` and `POST /plans/{id}/regenerate` that enqueue `prep_llm`. Ownership is checked on every resource.

## Decision

- Alembic `008_talk_plans` is reversible: create the three tables and add `sessions.talk_plan_id → talk_plans.id` (SET NULL).
- User PATCH edits increment `version` and append a field-name history row (no prompt or transcript text).
- `POST /regenerate` versions the same way, records `feedback_chars` only, and enqueues `tasks.prep_llm` on the `llm` queue.
- The worker writes a **placeholder** `outputs` object so the row is `ready`. `prep_*` LLM bodies are issues #56–#62.
- Missing or foreign plans return 404 (no existence leak).
- `GET /plans/{id}/objectives-scores` is empty until the #62 check engine writes rows.
- `POST/GET /goals` stays issue #65; this migration only creates the table.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Generate full prep outputs in this PR**  
   - ❌ That is #56–#62; this issue is the data model and API

2. **Return 403 for another user's plan**  
   - ❌ Leaks that the id exists

## Consequences

- Compose `alembic upgrade head` creates the Phase 3 tables.
- Sibling issues that need these tables (#56–#65) wait for this PR to merge.
