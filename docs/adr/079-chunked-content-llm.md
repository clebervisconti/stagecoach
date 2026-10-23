# ADR-079: Chunked content_llm with a wall-clock budget

**Date:** 2026-10-23
**Status:** Accepted
**Phase:** O2
**Issue:** #160

## Context

On a 120 s fixture, `content_llm` took 244 s with local Qwen because five prompts each ran k=3 against the whole transcript (ADR-078 addendum). `chunk_segments` existed and was never called. A 60-minute webinar is on the order of 12k transcript tokens, so the same pattern is about 95–120 minutes, or the 180 s local timeout fires and the whole content stage becomes N/A. `cost_ceiling_per_analysis` does not trip when local prices are $0. The processing timeline showed one `content_llm` row at pct 87 with no chunk detail.

## Decision

- Map each live transcript prompt (`outline_v1`, `message_v1`, `story_impact_v1`, `audience_clarity_v1`) over `chunk_segments` at ≤6k tokens (about 4 characters per token, including the numbered line). Reduce the per-chunk JSON to the existing stage schema with one merge call. If the merge payload itself exceeds 6k tokens, merge in halves and trim strings. Never send the whole transcript once it is over the 8k token cap. A single segment that is already over the cap cannot be split without breaking its ID, so it is still sent and logged.
- `open_close_v1` stays the first 60 s and the last 90 s. Those windows are trimmed from the inner edge if they would exceed 8k tokens.
- Short sessions (duration ≤ 12 minutes and estimated transcript tokens ≤ 6k) keep today's direct call at k=3. Longer sessions use k=1 for map and reduce. Quote, segment-id, and emotion-term checks still run on the reduced output (and on each map output before the merge).
- `content.json` `provenance` records `k`, `chunk_count`, `long_session`, `budget_s`, `partial`, `completed_prompts`, and `unfinished_prompts`. Chunks that finished before a merge are stored under `provenance.chunks`.
- Wall clock defaults to 8 minutes (`CONTENT_LLM_BUDGET_S`, or the `budget_s` argument). The check is before the next model call, so the in-flight call finishes. The stage then writes what it has and returns `succeeded` with `partial: true` and a timeline message that names the finished prompts and says unfinished ones stay N/A. Fusion already omits missing prompt blocks, so those categories are N/A and completed ones still score. The analysis job is not failed. A model error before any prompt still writes `unavailable` content. A model error after a prompt finished keeps the partial file.
- Progress stays one `content_llm` step in `PIPELINE_STAGES`. The stage message is `outline 1/2`, then `outline reduce`, and pct moves from 87 toward 88. The first finished prompt emits `partial_ready` after a fusion refresh so the report can show the new scores.
- `online_flow_v1` (online SPEC §11) is one bounded coaching call. It is not map-reduced, and this change does not wire it.

## Alternatives considered

1. **Raise the 180 s local timeout and send the whole webinar transcript**
   - Still about 15 long prefills. A 27B local call on 12k tokens is the two-hour case this issue exists to avoid.

2. **Celery `time_limit` that kills the worker mid-call**
   - Drops the in-flight result and can fail the job. The budget stops between calls instead.

3. **k=1 for every session**
   - Short talks already finish in a few minutes at k=3, and that self-consistency is the SPEC default.

4. **A new timeline stage per chunk**
   - The processing list would grow with the talk. The message on the existing `content_llm` row is enough.

## Consequences

- A long synthetic transcript in CI finishes under the budget with a mocked model, or stops with partial `content.json`. No live 60-minute LLM run.
- Local calls see a chunk, not the whole webinar transcript, once the transcript is over the cap.
- A budget stop leaves a succeeded content step with an explicit partial message instead of a silent all-N/A file.
- The first finished prompt refreshes fusion once. Later prompts land in the final fusion.
