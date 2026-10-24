# ADR-081: Editable layout save, multi-segment crops, and ASR reuse

**Date:** 2026-10-23
**Status:** Accepted
**Phase:** O2
**Supersedes in part:** ADR-071 (read-only layout review)

## Context

Phase O2 lets a person correct camera and screen boxes and the analysis window, then re-analyse without uploading again. The same job must not transcribe a second time when the window is unchanged. A recording can change framing, so one segment is no longer enough. Cropping every span into one file is a poor fit for ffmpeg when the boxes differ in size.

## Decision

- `PUT /sessions/{id}/layout` validates regions (at least 5% of the frame, one camera and one screen per segment), contiguous coverage, and an analysis window of at least 60 seconds inside the recording. The body carries the layout `version`. A mismatch returns 409 and does not write. A match writes `layout.json`, bumps the version, sets the session window, and enqueues `tasks.run_mvp_analysis` with `skip_ingest=True`.
- `edit_count` compares the save with the original detected document. Zero edits are `confirmed`. Any edit is `corrected`.
- `POST /sessions/{id}/reanalyse-layout` opens a new analysis job, copies ingest by path (not the transcript), and seeds version 1 from the confirmed layout. The previous job stays. The editor then saves with the normal PUT.
- ASR reuse hashes language, window, and stage version. When that hash matches a sibling job, the worker copies `transcript.json` and does not call the transcriber. A changed window is cut with ffmpeg `-ss`/`-to` as argv, transcribed, and shifted back to source time. Stage jobs (`skip_ingest` false) always transcribe.
- Switching folds frame signatures into stable runs. Runs shorter than three samples join a neighbour. Recordings with fewer than three samples stay one segment, so O1 fixtures do not split.
- Gallery layout picks the highest-score face as camera and marks the rest `other_participant`. A score gap under 0.1 sets `primary_speaker_unclear`. Mouth movement against VAD is not available yet because layout runs before aligned speech.
- Region crops keep using one box per role: the longest span. Every span is listed in the sidecar. A single-segment correction still changes `camera.mp4`.

## Alternatives considered

- Update the same job in place for re-analyse — rejected. A failed second pass would erase the report the person already has.
- Concatenate differently sized crops — rejected for this phase. The dominant span matches the O1 crop contract.
- Block save while Redis is down — rejected. The global API limiter still applies. The tighter layout bucket fails open.

## Consequences

- Re-analyse with the same window does not spend a second ASR pass.
- A trimmed window re-transcribes only that span. Word times stay on the source clock. Alignment still reads the full `audio16k`, so a short window can be a weaker alignment. That is recorded here rather than blocking O2.
- Multi-segment vision uses the longest camera span until a later phase concatenates spans.
