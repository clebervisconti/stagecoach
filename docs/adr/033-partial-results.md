# ADR-033: Partial results via SSE; vision failure degrades to audio/text

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 2

## Context

Issue #46 / SPEC §7.6, §6.10. Audio and text categories should render as stages finish (`partial_ready`). A vision-stage failure must not fail the job: the user still gets an audio+text report, and categories 12–14 (`gestures_body`, `eye_contact`, `facial_affect`) stay N/A with an explicit reason. Scores are never invented.

## Decision

- Progress events are SPEC-shaped: `type: stage | partial_ready | done`.
- After ASR + audio features, fusion writes `report.json` and emits `partial_ready` with the scored category ids. `GET /sessions/{id}/report` then succeeds while the session is still `processing`.
- Vision and slides run after that first pass. Vision exceptions write `vision_status.json` `{status: failed}` and the pipeline continues. Final fusion maps 12–14 to N/A with “Vision stage failed…” when consent had allowed vision. Consent-off reasons still win.
- The report page listens to SSE and also polls `/report` during processing, so cards update live. Processing chrome stays until the job is terminal.

## Alternatives considered

1. **Fail the job when vision fails**  
   - ❌ SPEC §6.10: non-critical stages produce a partial report

2. **Wait for vision before any scores**  
   - ❌ SPEC §7.6: audio/text categories usually arrive first

3. **Invent zeros for body categories when vision fails**  
   - ❌ N/A rule; zeros would look like a measured poor performance

## Consequences

- Users see pace/fluency/vocal-variety cards before pose finishes
- A MediaPipe crash still yields a usable audio/text report
- Body cards stay grey with a reason instead of a fake score
