# ADR-071: O1 wizard, prepare_session, and read-only layout review

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1

## Context

Phase O1 must ship a walking skeleton for webinar / online talk / recorded video without changing the stage upload form when the flag is off.

## Decision

- Full-page wizard at `/sessions/new?step=where|recording` when `online_modes_enabled` is true for the account. Stage users without the flag keep the inline form.
- One file only. No tab bar. Deck uploads before the recording. Rights checkbox for webinar and online talk, and for recorded video only when "other people appear" is ticked.
- `tasks.prepare_session` runs ingest + single-layout detection, then either waits at `layout_review` or enqueues `tasks.run_mvp_analysis` with `skip_ingest=True`.
- Layout review is read-only. ADJUST and trim stay hidden. Empty (`no_regions_found`) uses ANALYSE AUDIO ONLY as the primary action.
- OD-3: first 3 confirmed online layouts always review; afterwards only when confidence < 0.80 or a review reason is set.
- Mobile H1 is 32/34 at 390 (proposed `heading-1` mobile step; not a new token).
- Layout preview JPEGs are private (`Cache-Control: private, no-store`). Server-side blur of ignore regions is O2.

## Alternatives considered

Always-on wizard for stage — rejected, scenario 12 requires the existing e2e path.
Tab bar with a single ONE FILE tab — rejected (answer 2).
