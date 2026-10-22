# ADR-061: Delivery modes and scoring config 1.1.0

**Date:** 2026-10-22  
**Status:** Accepted  
**Phase:** O0  
**Owner decision:** OD-1 (a), OD-9 (a), 22 Oct 2026

## Context

Stage Coach scored one kind of recording. Online talks need different category weights without forking the engine or changing stage results.

## Decision

- `delivery_mode` is orthogonal to `context_type`: `stage`, `webinar`, `online_talk`, `recorded_video`.
- Scoring config `v1.1.0` copies `v1.0.0` and adds `modes`, four categories (`screen_flow`, `on_camera_presence`, `online_engagement`, `production_quality`), pillar updates, and `core_delivery`.
- `effective_weights(config, context, mode)` applies mode multipliers, then takes the new-category share out of every existing weight. Stage multipliers and new-category shares are empty, so stage weights match 1.0.0.
- `ScoringEngine` takes `mode`. Curve order is `mode_curves[mode]`, then `context_curves[context]`, then `curve`. A missing context curve falls back instead of raising.
- Stage parity is a CI gate (`packages/scoring/tests/unit/test_modes.py`).
- New-category weights are heuristic (H). Calibrate after 30 real sessions.

## Alternatives considered

1. **Merge webinar and online talk** — rejected (OD-1). Q&A and interaction weight differ.  
2. **Ship new categories at weight 0** — rejected (OD-9). They take part in overall once later phases fill the metrics.

## Consequences

- Live fusion can move to 1.1.0 with `mode="stage"` without changing stage scores.
- Online modes stay behind `ONLINE_MODES_ENABLED` until O4.
