# Use ECR mirror for base image to avoid Docker Hub rate limits
FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg for media processing
# Plus pkg-config and ffmpeg dev libraries for building PyAV (faster-whisper dep)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
# Upgrade pip first for better wheel support
RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directory for processing
RUN mkdir -p /tmp/stagecoach

# Make packages available
ENV PYTHONPATH=/app:/packages

CMD ["celery", "-A", "worker.app", "worker", "-Q", "cpu", "--loglevel=info"]
