# ADR-063: Region-cropped analysis and other participants

**Date:** 2026-10-22  
**Status:** Accepted  
**Phase:** O0 (decision only; implementation is O1)

## Context

A composite camera tile is too small on the 1280 px analysis proxy.

## Decision

Crops come from the original upload (`camera.mp4`, `screen.mp4`). `other_participant` and `ignore` regions never reach vision. Preview JPEGs follow media retention. No frames go to any LLM.

## Alternatives considered

1. **Analyse the full composite** — rejected; faces are 40–60 px.  
2. **Send keyframes to a vision LLM** — rejected; text-only (ADR-060).
