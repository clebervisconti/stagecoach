# ADR-042: Phase 2 exit fixtures and CPU bench

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 2  
**Issue:** #54

## Context

Phase 2 AC asks for stage / to-camera / screen-recording fixtures with the right N/A matrix, a vision benchmark (s per media-minute, CPU and GPU) in DECISIONS.md, P50 end-to-end ≤ 1.5× media duration on CPU, plus `docs/demos/phase-2.md` and CHANGELOG.

## Decision

- Add `tests/test_phase2_exit.py`: three synthetic fixtures (not personal recordings) prove applicable vs N/A and non-zero confidence.
- CPU fusion-only P50 stand-in must be ≤ 1.5× on the synthetic transcript duration. Measured here: **0.09 s / 228 s ≈ 0.0004×**.
- Vision CPU bench on scripted detections (no decode, no MediaPipe graph): **≈ 0.5 s per media-minute**.
- CHANGELOG is updated. Benchmark numbers live in this ADR and `docs/demos/phase-2/54.md`.
- `docs/DECISIONS.md` and `docs/demos/phase-2.md` are **not** edited on this branch (sibling-PR convention from Phase 2). Owner can copy the numbers.

## Owner / hardware flags

1. **GPU bench** — this CI is CPU-only. No GPU s/media-minute.
2. **Full-pipeline P50** — ingest + ASR + vision + LLM on a 20-min talk was not run. The 1.5× assertion is fusion/scoring only.
3. **DECISIONS.md / phase-2.md** — AC names them; this repo’s Phase 2 convention keeps those files for the owner. Numbers are in this ADR.

## Alternatives considered

1. **Claim 1.5× on a 2 s clip of full vision+ASR**  
   - ❌ Not representative; would fail or be faked

2. **Edit DECISIONS.md here**  
   - ❌ Conflicts with the established sibling-PR doc convention
