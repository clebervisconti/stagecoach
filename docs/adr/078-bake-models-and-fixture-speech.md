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
4. **Bake wav2vec2 alignment weights** — done in the 2026-10-23 addendum
   after the egress-blocked LION run failed with `URLError` on the
   torchaudio checkpoint. Both en and pt-BR now bake; offline smoke runs
   alignment.

## Consequences

- A missing `nltk` fails worker CI (`test_whisperx_imports_nltk_and_pandas`
  and the speech alignment test).
- Online fixture tests assert ASR word count > 0 and alignment succeeded.
- `docker run --network=none … python scripts/offline_runtime_smoke.py`
  loads the baked models without outbound HTTP.

## Addendum (2026-10-23): alignment checkpoints, camera-crop YuNet, content_llm scale

Cyberlabs' 120 s `composite_pip_tr` run on LION after #158 (egress blocked)
failed English alignment with `URLError` — torchaudio still downloaded
`wav2vec2_fairseq_base_ls960_asr_ls960.pth` (~378 MB). Portuguese would have
hit Hugging Face for whisperX's default `pt` model. `face_visible_ratio` was
0.0 even though layout YuNet found the tile (camera IoU 0.98). The OpenCV
5.0.0 `setPreferableTarget Targets are not supported` warning still printed
at worker start.

### Decision

- Bake `WAV2VEC2_ASR_BASE_960H` into `TORCH_HOME/hub/checkpoints` with
  SHA-256 `488fd4f16de84438ffc945334278c1b9fb9b7159a806c1080b16111a958c945d`.
- Bake whisperX `DEFAULT_ALIGN_MODELS_HF["pt"]`
  (`jonatasgrosman/wav2vec2-large-xlsr-53-portuguese`, Apache-2.0) under
  `/models/alignment/…`, not `HF_HOME` (that path is a Compose volume).
  Cleber speaks en and pt-BR; both languages must align offline.
- `offline_runtime_smoke.py` loads both alignment models with
  `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` and **runs** `whisperx.align`
  on the committed espeak-ng clip (not imports only).
- Camera-crop YuNet: `measure_face_visible_ratio` decodes `camera.mp4` at
  native width (layout still samples the full frame at 960). The 2023mar
  model is for 10–300 px faces (ADR-062). A 320×240 PiP crop stretched to
  960 px makes the synthetic face ~700 px, so YuNet returns nothing.
  `YuNetFaceDetector` upscales only when the short side is below 320
  (tiny 640×360 test clips) and letterbox-pads otherwise.
- The `setPreferableTarget` warning comes from **YuNet's** FaceDetectorYN
  net (the only `cv2.dnn` net in-tree). OpenCV 5.0.0 still logs it from the
  ONNX NMS node after `DNN_BACKEND_OPENCV` / `DNN_TARGET_CPU`. Inference
  stays on CPU. The C++ logger is quieted only around `create` /
  `setInputSize`.

### Image size

English wav2vec2 base is **377 664 473** bytes (~360 MiB). Portuguese
`pytorch_model.bin` is **1 262 122 456** bytes (~1.18 GiB) plus a few
kilobytes of tokenizer JSON. Expect the worker image to grow by about
**1.5 GiB** on both amd64 and arm64, on top of the ADR-078 ~0.5 GiB.

### content_llm scale (measurement only)

On the 120 s fixture, `content_llm` took **244 s** with local Qwen
(`qwen/qwen3.8-27b`). The stage does **not** chunk: `chunk_segments`
(6k-token helper) is unused. Five prompts (`outline_v1`, `message_v1`,
`story_impact_v1`, `audience_clarity_v1`, `open_close_v1`) each run **k=3**
→ **15** structured calls. `fluency_disambig_v1` and `qa_v1` are stubs.
`slides_v1` is the slides stage. Four prompts receive the **whole**
transcript; `open_close_v1` is first 60 s + last 90 s only.

A 60-minute webinar is ~30× the speech tokens of a 2-minute clip
(~9 000 words / ~12k tokens vs ~300 words). Average 244/15 ≈ 16 s/call
on the short clip. If prefill scales with tokens, the four full-transcript
prompts become ~12 × 16 s × 30 ≈ 96 minutes, plus ~48 s for open/close
→ **about 95–120 minutes** of `content_llm` (linear-with-duration
heuristic: 244 s × 30 ≈ 122 minutes).

**Timeouts / budgets.** Local HTTP timeout is **180 s per call**,
**one attempt** (retries are disabled for `local`). A 60-minute
whole-transcript prompt is likely to exceed 180 s and fail; 
`run_content_llm_safe` then writes content N/A and the job continues.
`cost_ceiling_per_analysis` is $0.50 but local token prices are $0, so
it never trips. There is **no** Celery `time_limit` on `content_llm` or
`run_mvp_analysis`, and no job-level wall-clock budget. The SSE stream
gives up at 600 s; the worker keeps going.

**Worst case.** If the 180 s timeout is raised or the model stays under
it: ~15 full-transcript 27B calls, **~90–120 minutes** for this stage
alone. If the timeout fires: the first long prompt dies at ~180 s, the
stage is marked unavailable, remaining pipeline stages still finish.
