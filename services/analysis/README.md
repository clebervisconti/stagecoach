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

## Development

```bash
# Install dependencies (amd64 CI / Linux x86). On Apple Silicon use
# requirements-torch-arm64.txt — torch==2.4.1+cpu has no aarch64 wheel.
pip install -r requirements-torch-amd64.txt
pip install -r requirements.txt

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
