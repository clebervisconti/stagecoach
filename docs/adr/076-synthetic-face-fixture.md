# ADR-076: Synthetic face on the composite fixture

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1

## Context

The O1 `composite_pip_tr` fixture was a tan rectangle on a slide. YuNet found no face, so layout classified `screen_full` (confidence 0.86) instead of `composite`. The fixture CLI could only emit the 2 s manifest clip, which is too short for real-stack timing (120 s / 60 min).

## Decision

- Put a **generated** frontal face (OpenCV ellipses, skin fill) in `tests/online/fixtures/assets/synthetic_face.png`.
- Licence: original work, [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Source and licence are recorded in `tests/online/fixtures/README.md`. Not a photograph and not a real person.
- Stretch the face to fill the PiP tile so YuNet detects it and `grow_tile` recovers the tile (camera and screen IoU ≥ 0.85).
- Add `--duration` and `--resolution` to `generate_online_fixtures.py` for 120 s and 60 min real-stack clips.

## Alternatives considered

1. **A CC0 photograph of a real person** — rejected for a public repo unless a licence and consent were already on file.
2. **Keep FakeFaceDetector only** — rejected; LION runs the real YuNet path.

## Consequences

- `test_yunet_detects_synthetic_face_and_classifies_composite` exercises the production detector.
- Timing fixtures stay uncommitted (`*.mp4` is git-ignored).
