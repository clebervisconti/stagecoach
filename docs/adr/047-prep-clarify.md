# ADR-047: Plan-a-talk form and prep_clarify_v1

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #56

## Context

SPEC §9.1 and §2.3 J3: the plan form is the main talk-prep input. Free-text description is extracted into structured fields; `prep_clarify_v1` asks at most five questions for missing critical fields (goal, slot, audience decision, plus roles and depth). Skip writes those as explicit assumptions.

## Decision

- Keep the extractor and question bank in the API (`app/prep_clarify.py`) so the API image does not import the worker package.
- `POST /plans/{id}/clarify` is a new router (does not edit `plans.py`). Ownership is 404 via `require_owned`.
- Tests use the stand-in extractor. A `generate` hook is the only live-LLM seam; CI never calls a paid model.
- `/prep` renders the §9.1 fields in en / pt-BR and posts through the existing BFF.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Put clarify in `services/analysis` and import it from the API**  
   - ❌ The API Docker image copies `services/api` only

2. **Ask more than five questions**  
   - ❌ Spec cap

## Consequences

- Message / structure / objectives (`#57`, `#58`, `#62`) stay in their own modules and do not write `outputs.clarify`.
