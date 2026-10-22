# Use GCR mirror to avoid Docker Hub / public ECR rate limits in CI
# Use Bookworm (Debian 12) for ffmpeg compatibility with av==11.*
FROM mirror.gcr.io/library/python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies including ffmpeg for media processing
# Plus pkg-config and ffmpeg dev libraries for building PyAV (faster-whisper dep)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    git \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
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

# Copy requirements and install Python dependencies
# Upgrade pip first for better wheel support
RUN pip install --upgrade pip

# Install base dependencies (including CPU-only torch) plus OTEL
COPY requirements.txt requirements-otel.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-otel.txt

# Install alignment dependencies (whisperx, pyannote)
# Force rebuild: 2026-10-09T23:45
COPY requirements-alignment.txt .
RUN pip install --no-cache-dir -r requirements-alignment.txt && \
    pip install --no-cache-dir --no-deps git+https://github.com/m-bain/whisperX.git@v3.8.6

# Copy application code
COPY . .

# Playwright Chromium for PDF export (SPEC §6.8 / §8.9). Apache-2.0 / BSD.
RUN playwright install-deps chromium && playwright install chromium

# MediaPipe Tasks models are downloaded on first vision run (Apache-2.0, SHA pinned).
ENV MEDIAPIPE_MODELS_DIR=/models
RUN mkdir -p /models

# Create temp directory for processing
RUN mkdir -p /tmp/stagecoach

# Make packages available
ENV PYTHONPATH=/app:/packages

CMD ["celery", "-A", "worker.app", "worker", "-Q", "cpu", "--loglevel=info"]
