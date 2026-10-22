# ADR-075: Bake YuNet into the worker image

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1
**Supersedes in part:** ADR-062 (download-on-first-use remains as fallback)

## Context

YuNet (`face_detection_yunet_2023mar.onnx`) downloaded into `/models` on first layout run. Recreating the container lost the file, so LION paid the download again and could fail offline.

## Decision

- Download YuNet during the worker image build into `/models`.
- Verify SHA-256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` (ADR-062). Fail the build on mismatch.
- Keep `ensure_models(..., include_layout=True)` as a runtime fallback.
- Do not mount a volume over `/models`. Production Compose mounts only `/models/huggingface` for the HF cache.

## Alternatives considered

1. **Commit the ONNX file** — rejected; ADR-062 keeps the model out of git.
2. **A persistent named volume at `/models`** — rejected; an empty volume hides the baked copy.

## Consequences

- Layout detection has the MIT YuNet weights on a fresh container.
- First-use download remains for hosts that are not using the image.
