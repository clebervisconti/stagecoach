# Use ECR mirror for base image to avoid Docker Hub rate limits
FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg for media processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directory for processing
RUN mkdir -p /tmp/stagecoach

# Make packages available
ENV PYTHONPATH=/app:/packages

CMD ["celery", "-A", "worker.app", "worker", "-Q", "cpu", "--loglevel=info"]
