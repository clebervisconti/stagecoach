# ADR-074: Offline Silero VAD load (no torch.hub prompt)

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1

## Context

Phase O1 on LION failed to load Silero VAD with `EOF when reading a line`. Newer `torch.hub.load` prompts `trust_repo` on stdin. The worker has no TTY, so the prompt raises EOF.

## Decision

- Prefetch Silero VAD **v6.2.3** at image build time into `/models/silero-vad`.
- Hash-check the GitHub tag tarball (`bc53dd7437f6f4a04e9bb946081b08db5ad8268df12ffaf10bc147c50294f95b`) and `silero_vad.jit` (`e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720`). Fail the build on mismatch.
- `load_silero_vad()` loads `source="local"` from `SILERO_VAD_DIR` / `/models/silero-vad` when `hubconf.py` is present.
- The GitHub hub fallback always passes `trust_repo=True`.
- A unit test asserts `input()` is never called and that a missing `trust_repo` would have raised EOF.

## Alternatives considered

1. **Only pass `trust_repo=True`** — necessary but not sufficient; the worker should not hit the network on every boot.
2. **Vendor the jit file in git** — rejected; keep models out of the public tree, same as YuNet.

## Consequences

- Alignment no longer depends on an interactive hub prompt.
- Runtime still works if the baked copy is missing (hub fallback with `trust_repo=True`).
