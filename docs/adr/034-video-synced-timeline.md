# ADR-034: Video-synced timeline lanes from existing artifacts

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 2

## Context

Issue #47 / SPEC §8.4. The report needs a horizontal track under the player with toggleable lanes (sections, slides, fillers, long pauses, rushing, monotone, gestures, audience-facing, smiles opt-in, CLT/story, Q&A), sprite hover, click-to-seek, two-way playhead sync, and J/L / Space / arrow keys.

## Decision

- Pure `pipeline/timeline.py` builds `timeline.json` from artifacts already on disk. Missing inputs leave a lane empty or unavailable. Spans are never invented.
- Smiles/flat-face items appear only when `expression_analysis` is granted. UI copy is “audience-facing”, never eye contact.
- Ingest sprites (every 5 s, 160px) are served at `GET /sessions/{id}/sprite?t=`. Hover uses those JPEGs.
- The player owns currentTime and the focused lane. J/L walk markers in the focused lane (evidence chips if no lane is focused). Space and ←/→ stay on the existing player map.

## Alternatives considered

1. **A new vision/audio model just for the strip**  
   - ❌ Extra licensed deps; the lanes are a view over metrics we already compute

2. **Always show a smiles lane from blendshapes without opt-in**  
   - ❌ SPEC and D8: expression signals are opt-in

3. **Put the timeline only in a tab**  
   - ❌ SPEC §8.1 / §8.4 place the strip under the player

## Consequences

- Audio-only sessions still get filler/pause/rushing/monotone/section lanes
- Sprite hover is a no-op 404 when ingest produced no sprites (audio-only)
- Keyboard shortcuts match the player region already documented for WCAG
