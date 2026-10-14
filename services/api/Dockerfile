# Use GCR mirror to avoid Docker Hub / public ECR rate limits in CI
FROM mirror.gcr.io/library/python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-otel.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-otel.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
