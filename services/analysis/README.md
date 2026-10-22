# Stage Coach Analysis Workers

Celery workers implementing the analysis pipeline.

## Stack

- **Queue**: Celery + Redis
- **Pipeline**: DAG of stages (ingest → ASR → audio features → LLM → scoring)
- **ASR**: faster-whisper + WhisperX alignment
- **Audio**: parselmouth (Praat), librosa
- **Vision**: MediaPipe Pose/Hand/Face (Phase 2)
- **Slides**: PySceneDetect, python-pptx / pdftotext, Tesseract (Phase 2)
- **LLM**: Provider-agnostic client with structured outputs

## Structure

```
pipeline/
  dag.py              - Celery chord/group definitions
  stages/             - Pipeline stage implementations
metrics/              - Pure metric functions (testable)
llm/                  - LLM client and providers
prompts/              - Versioned prompt templates
tests/
  unit/               - Metric function unit tests
  golden/             - Golden-file pipeline tests
  fixtures/           - Test media files
```

## Torch and arm64

The worker image must build on **linux/arm64** (LION / OrbStack) from this
tree. `torch==2.4.1+cpu` has no aarch64 wheel.

| Arch | Pin | Index |
|---|---|---|
| linux/amd64 | `torch==2.4.1+cpu`, `torchaudio==2.4.1+cpu` | `https://download.pytorch.org/whl/cpu` |
| linux/arm64 | `torch==2.4.1`, `torchaudio==2.4.1` | PyPI |

Install `requirements-torch.txt` (markers) or the arch-specific file
**before** `requirements.txt`. Alignment is installed with
`-c requirements-torch-$ARCH.txt` so pyannote cannot float torch.

The Dockerfile is multi-stage: `g++`, `make`, `ninja`, and
`CMAKE_POLICY_VERSION_MINIMUM=3.5` are build-only (parselmouth on arm64).
YuNet and Silero VAD are hash-checked into `/models` at build time.

```bash
# Host install (amd64 CI / local)
pip install -r requirements-torch.txt -r requirements.txt
```

## Development

```bash
# Install dependencies
pip install -r requirements-torch.txt -r requirements.txt

# Start worker (CPU queue)
celery -A pipeline.celery_app worker -Q cpu --loglevel=info

# Start worker (LLM queue)
celery -A pipeline.celery_app worker -Q llm --loglevel=info --concurrency=4

# Run tests
pytest
pytest tests/golden/  # Golden-file tests
```

## Phase Status

- Phase 0: Package structure only
- Phase 1: Ingest, ASR, content LLM, and audio features (`prosody.parquet` / pauses / syllables)
- Phase 2: Vision pipeline (`pose.parquet` / `face.parquet`, CPU MediaPipe, consent-gated)
