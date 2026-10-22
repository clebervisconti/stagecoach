# ADR-078: Bake remaining worker models and put speech on the online fixture

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1
**Supersedes in part:** ADR-075 (YuNet-only bake), ADR-076 (face-only fixture)

## Context

Cyberlabs ran a 120 s `composite_pip_tr` webinar fixture on LION after #157.
Word alignment died with `ModuleNotFoundError: No module named 'nltk'` because
whisperX is installed `--no-deps`. The fixture audio was silence, so ASR
returned 0 words and alignment never ran. MediaPipe `.task` files and
`Systran/faster-whisper-small` still downloaded on first use. `face_visible_ratio`
was `null` even though layout classified `composite` (0.871): fusion used
`or`, so a MediaPipe 0.0 (or a missing `vision_quality.json`) became `None`,
and YuNet on the camera crop was never mapped into the report.

## Decision

- Pin every module whisperX 3.8.6 actually imports (`nltk`, `pandas`, plus the
  existing transformers / librosa / pyannote pins) in `requirements-alignment.txt`.
  The repo does not use `--require-hashes`.
- Prefetch NLTK `punkt_tab` and `punkt` into `/models/nltk_data` with SHA-256
  checks. Set `NLTK_DATA`.
- Prefetch MediaPipe pose / hand / face `.task` files (SHAs already in
  `MODEL_REGISTRY`) and `Systran/faster-whisper-small` (`model.bin` plus
  tokenizer files) into `/models`. Runtime `ensure_models` / HuggingFace
  download stays as fallback.
- Generate fixture audio with **espeak-ng** (`en-us`, original webinar text).
  Commit `tests/online/fixtures/assets/synthetic_speech.wav`. Licence: espeak-ng
  is GPL-3.0; the clip is synthetic TTS of original text, not a person's voice
  and not a recording of Cleber. Recorded in the fixtures README.
- Compute `face_visible_ratio` with YuNet on `camera.mp4` after the crop, and
  map the first non-`None` number (including `0.0`) into the report.
- Pin YuNet's OpenCV DNN backend/target to `DNN_BACKEND_OPENCV` /
  `DNN_TARGET_CPU`.
- `make lion-*` accepts `COMPOSE_PROJECT_NAME`, `ENV_FILE`, `LION_OVERRIDE`.
  `lion-up` starts `LION_SERVICES` and excludes `worker-beat`.

## Image size

Baking `faster-whisper-small` adds about **462 MiB** (`model.bin` 483 546 902
bytes). MediaPipe `.task` files add about **20 MiB**. NLTK tokenizers add
about **18 MiB** of zip payload (smaller on disk after extract). YuNet and
Silero were already baked (ADR-074, ADR-075). Expect the worker image to grow
by roughly **0.5 GiB** on both amd64 and arm64.

## Alternatives considered

1. **Install whisperX with dependencies** — rejected; its pyproject wants
   torch 2.8 and floats the ADR-073 pin.
2. **Piper voice** — acceptable (permissive voices exist) but espeak-ng is
   already used by `scripts/bench_phase1_cpu.py` and needs no extra voice file.
3. **A CC0 recording of a real person** — rejected for a public repo.
4. **Bake wav2vec2 alignment weights** — deferred; alignment can still
   download `WAV2VEC2_ASR_BASE_960H`. The job continues if alignment is
   skipped. Offline smoke covers ASR + YuNet + MediaPipe + NLTK + Silero.

## Consequences

- A missing `nltk` fails worker CI (`test_whisperx_imports_nltk_and_pandas`
  and the speech alignment test).
- Online fixture tests assert ASR word count > 0 and alignment succeeded.
- `docker run --network=none … python scripts/offline_runtime_smoke.py`
  loads the baked models without outbound HTTP.
