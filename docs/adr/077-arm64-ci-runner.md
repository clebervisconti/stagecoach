# ADR-077: Native GitHub arm64 runner for the worker image

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1

## Context

CI built the worker image for `linux/arm64` with buildx + QEMU on `ubuntu-latest`. The first run on PR #157 took **6694 s (~112 min)** and produced a 4.06 GB image. That is too slow to stay in the default PR loop. Cyberlabs still needs the import smoke (`torch`, `torchaudio`, `parselmouth`, `mediapipe`, `cv2`) on arm64.

GitHub-hosted `ubuntu-24.04-arm` is free for public repositories.

## Decision

- Run `CI / Worker arm64 image` on **`ubuntu-24.04-arm`**. Drop QEMU.
- Cache buildx layers with `type=gha` (`scope=worker-arm64`, `mode=max`).
- On pull requests, build only when `services/analysis/` (the worker), `packages/`, any `Dockerfile`, any `requirements*.txt`, or `.github/workflows/ci.yml` change. On **pushes to `main`** (and `workflow_dispatch`) always build.
- Keep the import smoke test. Do not use a paid runner or a paid build service.

## Alternatives considered

1. **Keep QEMU on ubuntu-latest** — rejected. 112 min is not a practical PR gate.
2. **Build only the torch stage** — rejected for the default job. The LION failure was the full image (parselmouth, YuNet, Silero). Native arm64 makes the full build cheap enough.
3. **Self-hosted LION runner** — rejected for CI. LION is the lab host, not a public Actions runner.

## Consequences

- PRs that only touch the web app or docs skip the arm64 image job.
- A cache hit should rebuild far faster than a cold native compile of parselmouth.
- The QEMU figure (6694 s, 4,059,990,162 bytes) stays as the baseline we replaced.
