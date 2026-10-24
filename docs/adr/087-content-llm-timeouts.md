# ADR-087: Long-talk content analysis finishes when the local model is slow

**Date:** 2026-10-24
**Status:** Accepted
**Phase:** Online

## Context

On the LION host the 35:49 webinar finished the pipeline, and `content_llm` failed. Outline chunk 1 of 2 was about 10.4k transcript tokens. The read timeout to the local OpenAI-compatible model (LM Studio at `host.docker.internal:1234`) is 180 seconds for the whole completion. The call raised `LLMTimeoutError`. The stage then marked the model unavailable for the run and wrote every content category N/A. The 480 second step budget had no time left for a retry. The endpoint was healthy. It was slow.

Appendix C C4 says a job is succeeded when coverage is high and no stage failed, and partial otherwise. The worker always stored `succeeded`, so the session read `ready` while the report was partial.

## Decision

- Long talks (over 12 minutes or 6k tokens) chunk `outline_v1` at 2,500 tokens. The other map/reduce prompts stay at 6,000. `open_close_v1` stays a window.
- The local native chat call streams when the transport can. The read timeout is the gap between bytes, not the whole completion. A transport without streaming keeps one response.
- `CONTENT_LLM_TIMEOUT_S` sets the base read timeout (default 180). It scales with the chunk's token estimate and caps at 600. `CONTENT_LLM_BUDGET_S` sets the base wall clock (default 8 minutes). Each 4k tokens above 6k adds 90 seconds, capped at 30 minutes. An explicit `budget_s` argument stays exact. A base of 0 stays 0. Neither variable is required.
- A timed-out call is retried once if the budget is not already spent. If the retry times out, that chunk is dropped and the other chunks and prompts continue. One timeout does not mark the model unavailable for the run.
- A connection error on the first prompt, with nothing finished, still writes the unavailable content file.
- The job status is `partial` when the report is partial, coverage is under 0.6, or the content step failed or stopped early. The session status is then `partial`. A caller with no report still gets `succeeded`.

## Alternatives considered

- Raise the single 180 second timeout and keep 10k-token outline chunks. A slow local model still fails the whole stage, and a larger chunk is what made the first call miss the timeout.
- Retry every error, including a refused connection. That hides a down endpoint and spends the budget on calls that cannot succeed.
- Leave the session `ready` whenever the process exits 0. The report badge already said partial, and the session list said the job was done.

## Consequences

- A slow outline chunk no longer erases message, story, and audience scores that could still run.
- Re-analyse a session to pick up the new chunking. Stored reports keep their old content file until then.
- The UI names the missing categories from `na_reason` (ADR-088). There is no content-only retry endpoint. Online sessions can change the layout and re-analyse, which runs the pipeline again.
