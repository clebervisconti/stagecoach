#!/bin/bash
# Run database migrations
set -e

cd "$(dirname "$0")/../services/api"

echo "Running database migrations..."

# Check if DATABASE_URL is set
: "${DATABASE_URL:?DATABASE_URL is required}"

# Run migrations
alembic upgrade head

echo "✓ Migrations complete"

# Seed scoring config if needed
cd ../..
python scripts/seed_scoring_config.py
