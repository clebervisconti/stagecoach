# ADR-051: Plan deck review table and headline storyline

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #60

## Context

SPEC §9.5: a deck review extracts PPTX/PDF text and returns a per-slide `Slide | Issue | Fix` table plus suggested assertion titles, a headline storyline test, and minimal-text heuristics (H: ~25 words on non-data slides, ~40 words any slide, > 3 bullets).

## Decision

- Implement the review in `services/analysis/pipeline/prep_slides.py` on top of the existing `python-pptx` / `pdftotext` extractors.
- Heuristics and the storyline test are code. `slides_v1` is not called (no paid vision LLM in CI).
- Do not add `POST /plans/{id}/deck` on this branch (that would edit the plan API / `main.py` and conflict with the trends PR).
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Call live `slides_v1` for every deck**  
   - ❌ Paid / flaky; extract + heuristics lock the AC

2. **Wire the upload route here**  
   - ❌ Sibling conflict with the unmerged trends API

## Consequences

- After the trends PR merges, a follow-up can attach `review_deck(path)` to `talk_plans.outputs.slide_review`.
