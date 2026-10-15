# ADR-035: Body tab and Slides tab from existing artifacts

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 2

## Context

Issue #48 / SPEC §8.7. The report needs a Body tab (gesture heat, gesture-space silhouette, events, sway, yaw histogram, notes-down, opt-in expressivity, data-quality panel) and a Slides tab (filmstrip with dwell, words, title type, Glance level, reading overlap, facing-screen seconds, AI assertion titles).

## Decision

- Pure `pipeline/body_slides.py` builds `body.json` and `slides_tab.json` from artifacts already on disk. Missing inputs stay empty or N/A. Scores are never invented.
- Wrist-space density and yaw histogram bins are stored on `gesture_metrics.json` / `gaze_metrics.json` at vision time so the tabs do not decrypt pose/face parquet.
- Expressivity and smile/flat-face events appear only when `expression_analysis` is granted.
- Suggested assertion titles come only from `slides_v1` and are labeled AI. No heuristic title is invented when the LLM is absent.
- `GET /sessions/{id}/body`, `/slides`, and `/keyframe?i=` serve the view. Clicking a slide seeks the player.

## Alternatives considered

1. **Decrypt pose.parquet in the API to draw the silhouette**  
   - ❌ Extra key handling on the request path; vision already has wrist samples

2. **Always invent assertion titles locally**  
   - ❌ SPEC labels them AI; unavailable LLM stays N/A

3. **A new vision model just for the heat strip**  
   - ❌ The strip is a view over `activity_windows` already computed for category 12

## Consequences

- Audio-only and consent-off sessions render the Body tab as unavailable, not zeros
- Glance level and AI titles stay empty in CI (no LLM key)
- `docs/DECISIONS.md` is not edited on this branch (sibling-PR convention)
