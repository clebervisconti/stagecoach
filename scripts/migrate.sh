#!/bin/bash
# Run database migrations
set -e

cd "$(dirname "$0")/../services/api"

echo "Running database migrations..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://stagecoach:dev_password_change_in_prod@localhost:5432/stagecoach"
    echo "Using default DATABASE_URL: $DATABASE_URL"
fi

# Run migrations
alembic upgrade head

echo "✓ Migrations complete"

# Seed scoring config if needed
cd ../..
python scripts/seed_scoring_config.py
