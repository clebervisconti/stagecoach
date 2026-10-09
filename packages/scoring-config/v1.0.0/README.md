# Scoring Configuration v1.0.0

**Release Date:** 2026-10-09  
**Status:** Initial MVP release  
**Phase:** 0–2

## Summary

This is the foundational scoring configuration for Stage Coach MVP. All weights, curves, and thresholds are derived from the research sources in `docs/research/sources.md` or explicitly labeled as heuristic (H).

## Contents

- 17 evaluation categories across 6 pillars
- 60+ sub-metrics with scoring curves
- 6 context types with differentiated weights
- Minimum evidence rules per category
- Research source attributions

## Key Design Decisions

1. **Category weights per context** (§4.5 of SPEC):
   - Each context column sums to 100
   - Executive briefings emphasize clarity and answer-first (BLUF)
   - Keynotes emphasize storytelling, energy, and impact
   - Virtual meetings weight eye contact (to-camera) higher

2. **Sub-metric weights** (§4.4 of SPEC):
   - Within each category, sub-metric weights sum to 1.0
   - Weights reflect the relative importance and reliability of each signal

3. **Scoring curves**:
   - Piecewise-linear interpolation between anchor points
   - Target-band curves for metrics like WPM (best inside a band, falling off outside)
   - Research-derived breakpoints labeled with source key (e.g., S12)
   - Heuristic breakpoints labeled H

4. **Minimum evidence rules**:
   - Speech duration, word counts, frame counts
   - Categories become N/A when evidence thresholds aren't met

## Validation

This configuration passes the following tests (run via `pytest packages/scoring/tests/test_config.py`):

- ✅ All context weights sum to 100
- ✅ All category sub-metric weights sum to 1.0
- ✅ All source keys exist in `docs/research/sources.md`
- ✅ All curves are well-formed (sorted x, valid y ∈ [0, 100])
- ✅ JSON Schema validation

## Calibration Status

| Component | Status | Notes |
|---|---|---|
| Category weights | Heuristic | Based on domain expert judgment and research priorities |
| Filler curves (S12 breakpoints) | Research-anchored | 5/min and 12/min thresholds from Laske & DiGennaro Reed (2024) |
| PVQ bands | Initial estimate | Anchored on Hincks (2005) 11–24% range; requires calibration in Phase 4 |
| WPM bands | Heuristic | 130–160 range is practitioner convention; validation in Phase 1+ |
| Gesture & expressivity curves | Heuristic | All thresholds require validation study calibration |
| LLM level mapping | Heuristic | `score = 20*L - 10`; validated against human raters in Phase 4 |

## Changes from Existing Rubric

The prior Stage Coach rubric had 10 dimensions. This v1.0.0 expands to 17 categories with:

- **Split dimensions**: "Structure" now separate from "Message", "Opening & Close" is standalone
- **New categories**: "Impact & Persuasion" (CLTs), "Clarity & Concision" (Minto/HBR), "Energy & Presence" (fusion)
- **Refined metrics**: Storytelling includes vividness and contrast moves; Vocal Variety adds PVQ and emphasis detection
- **Context differentiation**: 6 contexts with distinct weights (vs. prior generic weights)

## Future Versions

Anticipated changes for v1.1.0+ (Phase 4):

- Calibrated PVQ, smile, and expressivity bands from validation study  
- Refined `f_pt` (pt-BR / en WPM factor) from corpus analysis  
- LLM level curves adjusted based on human–machine agreement  
- Personal baseline thresholds (from 3+ sessions)

## References

All source keys (S1–S56) are documented in `docs/research/sources.md`.
