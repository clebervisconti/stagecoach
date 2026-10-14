#!/usr/bin/env bash
# Read-only production probes. Never prints secrets.
set -euo pipefail

HOST="${1:-https://stagecoach.cybersphere.com.br}"
LOOPBACK="${2:-http://127.0.0.1:3107}"

echo "== loopback health (run on LION) =="
if curl -fsS "$LOOPBACK/api/health"; then
  echo
else
  echo "loopback health failed (expected if this is not LION)"
fi

echo
echo "== public Access gate =="
HEADERS="$(curl -sSI "$HOST/" || true)"
printf '%s\n' "$HEADERS" | head -n 20
if printf '%s\n' "$HEADERS" | grep -qiE 'HTTP/.* (302|401)'; then
  if printf '%s\n' "$HEADERS" | grep -qi 'cloudflareaccess.com'; then
    echo "PASS: unauthenticated public request is redirected to Cloudflare Access"
  else
    echo "WARN: got a challenge/redirect, but not clearly Cloudflare Access"
  fi
else
  echo "FAIL: public hostname did not challenge unauthenticated traffic"
  exit 1
fi
