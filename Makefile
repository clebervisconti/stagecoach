.PHONY: help install dev down logs test lint type clean migrate generate-types check-generated lion-build lion-config lion-up

LION_COMPOSE = docker compose -f docker-compose.yml -f infra/compose.lion.yaml --profile web --profile minio --profile workers

help:
	@echo "Stage Coach Development Commands"
	@echo ""
	@echo "  make install         - Install all dependencies"
	@echo "  make dev             - Start development environment (docker compose)"
	@echo "  make down            - Stop all services"
	@echo "  make logs            - View service logs"
	@echo "  make migrate         - Run database migrations"
	@echo "  make generate-types  - Generate types from JSON schemas"
	@echo "  make check-generated - Check if generated code is up to date (CI)"
	@echo "  make test            - Run all tests"
	@echo "  make lint            - Run linters"
	@echo "  make type            - Run type checkers"
	@echo "  make clean           - Clean build artifacts"
	@echo "  make lion-build      - Build API/web/worker images for LION (linux/arm64 or host)"
	@echo "  make lion-config     - Print merged LION compose (ports must be 8870/6380/9010)"
	@echo "  make lion-up         - Start the LION overlay (loopback 8870/6380/9010)"

install:
	@echo "Installing Python dependencies..."
	cd packages/scoring && pip install -e ".[dev]"
	@echo "Dependencies installed."

dev:
	@echo "Starting development environment..."
	docker compose up -d
	@echo ""
	@echo "Services started:"
	@echo "  API:           http://localhost:8000"
	@echo "  API docs:      http://localhost:8000/docs"
	@echo "  PostgreSQL:    localhost:5432"
	@echo "  Redis:         localhost:6379"
	@echo "  MinIO:         http://localhost:9000"
	@echo "  MinIO console: http://localhost:9001"

down:
	docker compose down

logs:
	docker compose logs -f

test:
	@echo "Running scoring engine tests..."
	cd packages/scoring && pytest -v
	@echo ""
	@echo "All tests passed!"

lint:
	@echo "Running ruff linter..."
	cd packages/scoring && ruff check .
	@echo "Lint checks passed!"

type:
	@echo "Running mypy type checker..."
	cd packages/scoring && mypy scoring/
	@echo "Type checks passed!"

migrate:
	@echo "Running database migrations..."
	bash scripts/migrate.sh

generate-types:
	@echo "Generating types from JSON schemas..."
	bash scripts/generate_types.sh

check-generated:
	@echo "Checking generated code..."
	bash scripts/check_generated.sh

lion-build:
	@echo "Building LION images (web=next start, API no reload, worker torch for this arch)..."
	$(LION_COMPOSE) build

lion-config:
	$(LION_COMPOSE) config --format json

lion-up:
	@echo "Starting LION overlay on 127.0.0.1:8870 (web), :6380 (Redis), :9010 (MinIO)..."
	$(LION_COMPOSE) up -d

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean complete."
