# ADR-032: Category 15 energy fusion from available modalities; no SER

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 2

## Context

Issue #45 / SPEC §4.4.15, §6.8. Metric ids must match `scoring.yaml` v1.0.0 (`ep_too_soft_ratio`, `ep_energy_trajectory`, `ep_key_moment_lift`, `ep_confident_language`, `ep_recovery`). Composite energy E(t) is the per-minute mean of z-scores of loudness, PVQ, gesture activity, and expressivity **whichever are available**. The reported trajectory is E(last third) − E(first third). This category must not be labeled confidence detection. Speech emotion recognition is not used.

## Decision

- Pure functions in `pipeline/energy.py`. Thresholds labeled heuristic (H).
- Fusion writes `energy_metrics.json` and maps only applicable rows onto `energy_presence`. Missing modalities are omitted so weights renormalize. Scores are never invented.
- Expressivity enters E(t) only when `expression_analysis` is granted. Gesture activity uses `activity_windows` from pose (no extra models).
- `ep_confident_language` and `ep_recovery` use LLM levels from `content.energy` when present. Recovery is N/A when no disruptions (long pauses ≥ 3 s or LLM-noted). No LLM → those two metrics stay N/A, never a made-up level.
- UI and artifacts say “energy and presence signals”, not confidence detection. No SER.

## Alternatives considered

1. **Ship an SER model for composure**  
   - ❌ SPEC §4.4.15 / §5.3 forbids SER here by default; license and emotion-inference risk

2. **Require all four modalities before scoring the category**  
   - ❌ The spec scores from whichever streams exist; audio-only talks still get loudness/PVQ

3. **Map hedge counts to `ep_confident_language` without an LLM**  
   - ❌ Unit is `llm_level`; inventing a level from a lexicon would fake an LLM judgment

## Consequences

- Category 15 can score from audio alone and gets richer when pose or opt-in expressivity exist
- Glance of E(t) is stored on `series_energy.json` for later graphs
- Recovery and language metrics stay N/A in CI (no LLM key)
