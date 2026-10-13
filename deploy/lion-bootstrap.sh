#!/usr/bin/env bash
# One-shot Stage Coach production bring-up. Run in a logged-in Terminal on LION
# (the login Keychain does not unlock over SSH). Idempotent: safe to re-run.
# Secrets are typed or pasted into hidden prompts; nothing is echoed or logged.
set -euo pipefail

APP_DIR="${STAGECOACH_DIR:-$HOME/cyberlabs/apps/stagecoach}"
REPO_URL="https://github.com/clebervisconti/stagecoach.git"
RUNNER="$HOME/cyberlabs/hosts/lion/stagecoach-run.sh"
PLIST="$HOME/Library/LaunchAgents/com.cyberlabs.stagecoach.plist"
LABEL="com.cyberlabs.stagecoach"
HEALTH_URL="http://127.0.0.1:3107/api/health"
export PATH="$HOME/.orbstack/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

step() { printf '\n== %s ==\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

has_secret() {
  security find-generic-password -a "$USER" -s "cyberlabs-$1" >/dev/null 2>&1
}

secret_length() {
  security find-generic-password -a "$USER" -s "cyberlabs-$1" -w 2>/dev/null | tr -d '\n' | wc -c | tr -d ' '
}

prompt_secret() {
  echo "Keychain item cyberlabs-$1 is missing. $2"
  security add-generic-password -a "$USER" -s "cyberlabs-$1" -U -w
}

generated_secret() {
  openssl rand -base64 48 | tr -d '\n' | pbcopy
  prompt_secret "$1" "A random value is on the clipboard: press Cmd+V, Enter, then Cmd+V, Enter again."
  pbcopy </dev/null
}

step "Preflight"
[[ "$(scutil --get ComputerName 2>/dev/null)" == *LION* ]] || fail "this is not LION ($(scutil --get ComputerName))"
[[ "$(stat -f %Su /dev/console)" == "$USER" ]] || fail "run this from $USER's logged-in GUI session, not SSH"
command -v docker >/dev/null || fail "docker CLI not found; expected ~/.orbstack/bin/docker (OrbStack)"
docker info >/dev/null 2>&1 || fail "OrbStack engine is not running; open OrbStack and retry"
docker compose version >/dev/null || fail "docker compose plugin missing"
if curl -fsS -o /dev/null http://127.0.0.1:13133/; then
  echo "OTel collector healthy on 127.0.0.1:13133"
else
  echo "WARN: OTel collector health check failed; telemetry will not arrive until com.cyberlabs.otel-collector is up"
fi
echo "OK: $(scutil --get ComputerName), user $USER, $(docker compose version --short)"

step "Repository at $APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch -q origin
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone -q "$REPO_URL" "$APP_DIR"
fi
git -C "$APP_DIR" checkout -q --detach origin/main
echo "main is $(git -C "$APP_DIR" rev-parse --short HEAD)"

step "Keychain items (values are never shown)"
has_secret POSTGRES_PASSWORD || generated_secret POSTGRES_PASSWORD
has_secret AUTH_SECRET || generated_secret AUTH_SECRET
has_secret PRIVATE_BETA_EMAIL || prompt_secret PRIVATE_BETA_EMAIL "Type the email address Cloudflare Access should allow."
has_secret CF_API_TOKEN || prompt_secret CF_API_TOKEN "Paste a Cloudflare API token with Access: Apps and Policies Edit, Cloudflare Tunnel Edit, DNS Edit, Zone Read."
[[ "$(secret_length AUTH_SECRET)" -ge 32 ]] || fail "cyberlabs-AUTH_SECRET must be at least 32 characters"
for item in POSTGRES_PASSWORD AUTH_SECRET PRIVATE_BETA_EMAIL CF_API_TOKEN; do
  echo "cyberlabs-$item present ($(secret_length "$item") chars)"
done
has_secret splunk-rum-token && echo "cyberlabs-splunk-rum-token present (browser RUM on)" \
  || echo "cyberlabs-splunk-rum-token absent (browser RUM off; server telemetry still on)"

step "LaunchAgent $LABEL"
mkdir -p "$(dirname "$RUNNER")" "$HOME/Library/LaunchAgents"
install -m 0755 "$APP_DIR/deploy/stagecoach-run.sh" "$RUNNER"
install -m 0644 "$APP_DIR/deploy/com.cyberlabs.stagecoach.plist" "$PLIST"
plutil -lint "$PLIST" >/dev/null
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$LABEL" || true
  docker compose -f "$APP_DIR/docker-compose.prod.yml" down || true
fi
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "started; logs: ~/Library/Logs/stagecoach.{out,err}.log"

step "Waiting for $HEALTH_URL (first build pulls models and can take 20+ minutes)"
deadline=$(( $(date +%s) + ${STAGECOACH_HEALTH_TIMEOUT:-2400} ))
until curl -fsS "$HEALTH_URL" 2>/dev/null; do
  (( $(date +%s) < deadline )) || { tail -n 40 "$HOME/Library/Logs/stagecoach.err.log" >&2; fail "web never became healthy"; }
  sleep 15
done
echo
docker compose -f "$APP_DIR/docker-compose.prod.yml" ps
if lsof -nP -iTCP:3107 -sTCP:LISTEN | awk 'NR>1 {print $9}' | grep -vqE '^127\.0\.0\.1:3107$'; then
  fail "port 3107 is listening beyond loopback"
fi
echo "OK: 3107 bound to loopback only"

step "Cloudflare (Access first, then tunnel hostname, then DNS)"
bash "$APP_DIR/deploy/cloudflare-private-beta.sh"
read -r -p "Apply the Cloudflare changes above? [y/N] " answer
if [[ "$answer" == [yY] ]]; then
  bash "$APP_DIR/deploy/cloudflare-private-beta.sh" --apply
  sleep 10
  bash "$APP_DIR/scripts/verify-live.sh"
else
  echo "Skipped. Re-run this script, or: bash deploy/cloudflare-private-beta.sh --apply"
fi
