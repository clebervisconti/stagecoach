# ADR-048: prep_message_v1 and audience table

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #57

## Context

SPEC §9.2–§9.3: three core-message candidates (≤ 15 words, claim vs topic, three tests), a CTA, 2–4 supporting points, `[needs source]` on numbers the user did not provide, plus the audience table, type adaptations, and a jargon list.

## Decision

- Implement the stand-in in `services/analysis/pipeline/prep_message.py` (worker image).
- Word-count clip is code, not the model. Tests never call a paid LLM; `generate` is an optional hook.
- Do not write `talk_plans.outputs` or touch the plan API / web form on this branch (those files belong to #55/#56).
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Let the LLM return any length and trust it**  
   - ❌ Spec: enforce ≤ 15 words

2. **Wire outputs into the plan row here**  
   - ❌ Sibling conflict with the unmerged plan form / clarify PR

## Consequences

- `prep_llm` can import `run_message` after #56 lands and the placeholder is replaced.
