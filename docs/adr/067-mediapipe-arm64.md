# ADR-067: MediaPipe 1.x for linux/arm64 (LION)

**Date:** 2026-10-22  
**Status:** Accepted  
**Phase:** O0  
**Owner decision:** OD-8 (a), 22 Oct 2026

## Context

`mediapipe==0.10.31` has no `linux/aarch64` wheel, so vision skipped on LION (PR #151). The 1.x line (1.1.1) publishes `manylinux_2_28_aarch64` wheels (S77). PR #153 already pinned 1.1.1 and added `libegl1`/`libgles2` to the worker image.

## Decision

- Keep **MediaPipe 1.1.1**, Apache-2.0.
- Keep the existing Tasks CPU API in `pipeline/vision/mediapipe_cpu.py` (`PoseLandmarker` / `FaceLandmarker` / `HandLandmarker`, VIDEO mode, CPU delegate).
- `mediapipe_available()` stays an import check so hosts without a wheel still skip cleanly.
- Rollback: pin `mediapipe==0.10.31` and accept vision skip on linux/arm64.

## Spike result (22 Oct 2026)

Recorded on the O0 agent host (`linux/x86_64`). Docker / buildx were not available, so a `linux/arm64` worker image was not rebuilt here.

```
$ python3 -c "import mediapipe as mp; from mediapipe.tasks.python import vision; print(mp.__version__)"
1.1.1
```

`pipeline/vision/mediapipe_cpu.py` still uses the Tasks CPU API. Worker tests including `tests/test_vision.py` and the three golden fixtures passed on 1.1.1 with no landmark-schema deltas versus the existing expected files.

Rollback remains: pin `mediapipe==0.10.31` and accept vision skip on linux/arm64. LION already installs 1.1.1 plus `libegl1`/`libgles2` (PR #153). Re-run `docker buildx build --platform linux/arm64` of `services/analysis/Dockerfile` on a host that has buildx, then `python -c "import mediapipe"` inside that image, before calling O0 closed on LION.

## Alternatives considered

1. **Stay on 0.10.31 / x86 only** — rejected (OD-8). On-camera categories would stay N/A in production.  
2. **Run vision on TIGER** — rejected for now. Face data would leave LION.

## Consequences

- Pose, face, and hands can run on the LION worker once the image is rebuilt.
- Golden re-baseline is required only if Tasks 1.1.1 changes landmark values beyond existing tolerances.
