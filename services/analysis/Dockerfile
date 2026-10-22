# Worker image. Builds on linux/amd64 and linux/arm64 from this file with no
# local override (ADR-073). Compilers stay in the build stage.
#
# torch==2.4.1+cpu has no aarch64 wheel. TARGETARCH selects the pin:
#   amd64 → PyTorch CPU index (+cpu)
#   arm64 → PyPI CPU wheels
# CMAKE_POLICY_VERSION_MINIMUM=3.5 lets praat-parselmouth's old CMake configure
# on Bookworm. g++ / make / ninja are required to build that wheel on arm64.

FROM mirror.gcr.io/library/python:3.11-slim-bookworm AS build

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    ninja-build \
    cmake \
    git \
    pkg-config \
    libpq-dev \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CMAKE_POLICY_VERSION_MINIMUM=3.5
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --upgrade pip

ARG TARGETARCH
COPY requirements-torch-amd64.txt requirements-torch-arm64.txt ./
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      pip install --no-cache-dir -r requirements-torch-arm64.txt; \
    else \
      pip install --no-cache-dir -r requirements-torch-amd64.txt; \
    fi

COPY requirements.txt requirements-otel.txt requirements-alignment.txt ./
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      CONSTRAINT=requirements-torch-arm64.txt; \
    else \
      CONSTRAINT=requirements-torch-amd64.txt; \
    fi && \
    pip install --no-cache-dir -r requirements.txt -r requirements-otel.txt && \
    pip install --no-cache-dir -r requirements-alignment.txt -c "$CONSTRAINT" && \
    pip install --no-cache-dir --no-deps git+https://github.com/m-bain/whisperX.git@v3.8.6 && \
    python -c "import torch, torchaudio; assert torch.__version__.startswith('2.4.1'), torch.__version__; assert torchaudio.__version__.startswith('2.4.1'), torchaudio.__version__"

COPY . .

ENV MEDIAPIPE_MODELS_DIR=/models
ENV SILERO_VAD_DIR=/models/silero-vad
ENV FASTER_WHISPER_DIR=/models/faster-whisper
ENV NLTK_DATA=/models/nltk_data
RUN python scripts/prefetch_models.py && \
    python -c "from pathlib import Path; \
root=Path('/models'); \
needed=[ \
  root/'face_detection_yunet_2023mar.onnx', \
  root/'silero-vad'/'hubconf.py', \
  root/'pose_landmarker_full.task', \
  root/'hand_landmarker.task', \
  root/'face_landmarker.task', \
  root/'faster-whisper'/'small'/'model.bin', \
  root/'nltk_data'/'tokenizers'/'punkt_tab'/'english'/'abbrev_types.txt', \
]; \
missing=[str(p) for p in needed if not p.is_file()]; \
assert not missing, missing"

FROM mirror.gcr.io/library/python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Runtime libs only — no g++, make, ninja, or cmake.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    libpq5 \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    libegl1 \
    libgles2 \
    libsm6 \
    libxext6 \
    libxrender1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-por \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local /usr/local
COPY --from=build /models /models
COPY --from=build /app /app

# Playwright Chromium for PDF export (SPEC §6.8 / §8.9). Apache-2.0 / BSD.
RUN playwright install-deps chromium && playwright install chromium

ENV MEDIAPIPE_MODELS_DIR=/models
ENV SILERO_VAD_DIR=/models/silero-vad
ENV FASTER_WHISPER_DIR=/models/faster-whisper
ENV NLTK_DATA=/models/nltk_data
ENV PYTHONPATH=/app:/packages

RUN mkdir -p /tmp/stagecoach

CMD ["celery", "-A", "worker.app", "worker", "-Q", "cpu", "--loglevel=info"]
