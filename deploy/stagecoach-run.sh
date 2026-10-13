#!/usr/bin/env bash
# LION production runner. Secrets come from the login Keychain, never from git.
set -euo pipefail

APP_DIR="${STAGECOACH_DIR:-$HOME/cyberlabs/apps/stagecoach}"
COMPOSE_FILE="${APP_DIR}/docker-compose.prod.yml"

# launchd does not inherit a login PATH. OrbStack's CLI is the only docker on LION.
export PATH="${HOME}/.orbstack/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

secret() {
  security find-generic-password -a "$USER" -s "cyberlabs-$1" -w
}

cd "$APP_DIR"
git fetch origin
git checkout --detach "origin/main"

export POSTGRES_PASSWORD
export AUTH_SECRET
export PRIVATE_BETA_EMAIL
POSTGRES_PASSWORD="$(secret POSTGRES_PASSWORD)"
AUTH_SECRET="$(secret AUTH_SECRET)"
PRIVATE_BETA_EMAIL="$(secret PRIVATE_BETA_EMAIL)"
export PRIVATE_BETA_MODE=true
export STAGECOACH_PORT=3107
export ASR_MODEL="${ASR_MODEL:-tiny}"
export MAX_UPLOAD_BYTES="${MAX_UPLOAD_BYTES:-83886080}"
export AUTH_TRUST_HOST=true

exec docker compose -f "$COMPOSE_FILE" up --build --remove-orphans
