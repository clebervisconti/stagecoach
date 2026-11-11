# ADR-091: Prepare speech recognition on another host, and leave it off

**Date:** 2026-11-11
**Status:** Accepted
**Phase:** 1.0 prep

## Context

ADR-0002 runs faster-whisper on the LION worker for the private beta. The backlog item is to move speech recognition to TIGER. Production compose and `deploy/stagecoach-run.sh` still default `ASR_MODEL` to `tiny`. The Python default, when that variable is unset, is `small`. Flipping the live model or the live host needs the owner. This change does not deploy and does not set a host.

## Decision

- `ASR_BACKEND` defaults to `local`. The only value that sends audio off the worker is `http`. Any other value, including a typo, stays on faster-whisper.
- `ASR_HTTP_URL` is read only when the backend is `http`. It must be an absolute http(s) URL with a host and no username, password, query, or fragment. A URL that ends at `/` or `/v1` gains `/audio/transcriptions`. Any other path is used as given. Missing URL fails the step. It does not fall back to local, so a half-set cutover is visible. A URL left in the environment while the backend is `local` is ignored.
- The client POSTs the session audio once, with `response_format=verbose_json`. Redirects are not followed. The response is capped at 16 MiB. `ASR_HTTP_TOKEN`, when set, is sent as a bearer token and must not appear in logs or in `transcript.json`.
- A remote word with no probability is stored as 1.0. The screen-flow guard drops words under 0.4, and a missing field would otherwise erase the transcript.
- Reuse of an earlier transcript (ADR-081) keeps the same hash while the backend is `local`. An `http` backend hashes separately, so a local transcript is not reused after the cutover.
- Compose passes `ASR_BACKEND`, `ASR_HTTP_URL`, and `ASR_HTTP_TOKEN` through with empty or `local` defaults. No host, token, or model change is committed. `ASR_MODEL` stays `${ASR_MODEL:-tiny}` in production.

## Alternatives considered

- Change the production default from `tiny` to `small` in the same change. That still runs on LION, and the owner has not cut that release.
- Put a TIGER hostname in `.env.example` or compose. The repo is public, and this change must not point the worker at a machine.
- Fall back to local faster-whisper when the URL is missing. A selected remote backend that silently stays local hides a broken cutover.

## Consequences

- Jobs behave as they do today while `ASR_BACKEND` is unset or `local`.
- Turning the HTTP path on sends session audio to whatever host the owner configures. That is an owner decision (backlog `SC-REL-001`). Do not set the variables on LION as part of this change.
- A live timing on TIGER was not run. The client is covered by unit tests with a fake transport.
