#!/usr/bin/env bash
# Create Access (first) then tunnel hostname + DNS for Stage Coach.
# Loads credentials from Apple Keychain. Never prints the token.
# Usage:
#   deploy/cloudflare-private-beta.sh              # discovery / dry-run
#   deploy/cloudflare-private-beta.sh --apply      # mutate
set -euo pipefail

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

secret() {
  security find-generic-password -a "$USER" -s "cyberlabs-$1" -w
}

# cyberlabs-cloudflare-api is the lab's shared token (Keychain copy of the Vaultwarden item).
CF_API_TOKEN="$(secret cloudflare-api 2>/dev/null || secret CF_API_TOKEN 2>/dev/null || true)"
if [[ ${#CF_API_TOKEN} -lt 20 ]]; then
  echo "neither cyberlabs-cloudflare-api nor cyberlabs-CF_API_TOKEN holds a usable token" >&2
  exit 1
fi

ACCOUNT_ID="${CF_ACCOUNT_ID:-${CF_ACCOUNT_ID_CLEBER:-}}"
HOSTNAME="stagecoach.cybersphere.com.br"
ORIGIN="http://127.0.0.1:3107"
ACCESS_EMAIL="${STAGECOACH_ACCESS_EMAIL:-$(secret PRIVATE_BETA_EMAIL)}"

cf() {
  local method="$1"
  local path="$2"
  shift 2
  curl -sS -X "$method" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4${path}" \
    "$@"
}

parse() {
  python3 -c "$1"
}

echo "== zones =="
ZONES_JSON="$(cf GET "/zones?per_page=50")"
printf '%s' "$ZONES_JSON" | parse '
import json,sys
data=json.load(sys.stdin)
assert data.get("success"), data
for z in data.get("result", []):
    print("{}\t{}".format(z["name"], z["id"]))
'

ZONE_ID="$(printf '%s' "$ZONES_JSON" | parse '
import json,sys
data=json.load(sys.stdin)
for z in data.get("result", []):
    if z["name"] == "cybersphere.com.br":
        print(z["id"])
        raise SystemExit
raise SystemExit("zone cybersphere.com.br not found")
')"
echo "zone_id length=${#ZONE_ID}"

if [[ -z "$ACCOUNT_ID" ]]; then
  ACCOUNT_ID="$(printf '%s' "$ZONES_JSON" | parse '
import json,sys
data=json.load(sys.stdin)
for z in data.get("result", []):
    if z["name"] == "cybersphere.com.br":
        print(z["account"]["id"])
        raise SystemExit
raise SystemExit("account id missing")
')"
fi
echo "account_id length=${#ACCOUNT_ID}"

echo
echo "== existing Access apps (name + host only) =="
APPS_JSON="$(cf GET "/accounts/${ACCOUNT_ID}/access/apps?per_page=50")"
printf '%s' "$APPS_JSON" | parse '
import json,sys
data=json.load(sys.stdin)
assert data.get("success"), data
for app in data.get("result", []):
    print("{}\t{}\t{}".format(app.get("name"), app.get("domain"), app.get("id")))
'

APP_ID="$(printf '%s' "$APPS_JSON" | parse '
import json,sys
data=json.load(sys.stdin)
for app in data.get("result", []):
    if app.get("domain") == "stagecoach.cybersphere.com.br":
        print(app["id"])
        break
')"

APP_BODY="$(ACCOUNT_PLACEHOLDER=1 python3 -c 'import json; print(json.dumps({
  "name": "Stage Coach",
  "domain": "stagecoach.cybersphere.com.br",
  "type": "self_hosted",
  "session_duration": "24h",
  "auto_redirect_to_identity": True,
  "app_launcher_visible": True,
}))')"

echo
echo "== Access app payload =="
echo "$APP_BODY"

if [[ -z "$APP_ID" && "$APPLY" -eq 1 ]]; then
  echo "creating Access application"
  CREATE_APP="$(cf POST "/accounts/${ACCOUNT_ID}/access/apps" --data "$APP_BODY")"
  APP_ID="$(printf '%s' "$CREATE_APP" | parse '
import json,sys
data=json.load(sys.stdin)
assert data.get("success"), data
print(data["result"]["id"])
')"
  echo "created app id length=${#APP_ID}"
elif [[ -z "$APP_ID" ]]; then
  echo "dry-run: would create Access application for $HOSTNAME"
fi

POLICY_BODY="$(ACCESS_EMAIL="$ACCESS_EMAIL" python3 -c 'import json,os; print(json.dumps({
  "name": "allow-owner",
  "decision": "allow",
  "include": [{"email": {"email": os.environ["ACCESS_EMAIL"]}}],
}))')"

if [[ -n "${APP_ID:-}" ]]; then
  echo "access app id length=${#APP_ID}"
  POLICIES="$(cf GET "/accounts/${ACCOUNT_ID}/access/apps/${APP_ID}/policies")"
  POLICY_COUNT="$(printf '%s' "$POLICIES" | parse '
import json,sys
data=json.load(sys.stdin)
assert data.get("success"), data
print(len(data.get("result", [])))
for p in data.get("result", []):
    print(p.get("name"), p.get("decision"), p.get("id"), file=sys.stderr)
')"
  if [[ "$POLICY_COUNT" == "0" && "$APPLY" -eq 1 ]]; then
    echo "creating allow policy"
    ACCESS_EMAIL="$ACCESS_EMAIL" POLICY_BODY="$POLICY_BODY" \
      cf POST "/accounts/${ACCOUNT_ID}/access/apps/${APP_ID}/policies" --data "$POLICY_BODY" \
      | parse 'import json,sys; d=json.load(sys.stdin); assert d.get("success"), d; print("policy created")'
  elif [[ "$POLICY_COUNT" == "0" ]]; then
    echo "dry-run: would create allow policy for $ACCESS_EMAIL"
  fi
fi

if [[ "$APPLY" -eq 1 ]]; then
  # Never publish a hostname without a gate in front of it.
  [[ -n "${APP_ID:-}" ]] || { echo "Access application missing; refusing to touch tunnel or DNS" >&2; exit 1; }
  GATED="$(cf GET "/accounts/${ACCOUNT_ID}/access/apps/${APP_ID}/policies" | parse '
import json,sys
data=json.load(sys.stdin)
print(sum(1 for p in data.get("result", []) if p.get("decision") == "allow"))
')"
  [[ "$GATED" -ge 1 ]] || { echo "Access app has no allow policy; refusing to touch tunnel or DNS" >&2; exit 1; }
  echo "Access gate confirmed (${GATED} allow policy)"
fi

echo
echo "== tunnels =="
TUNNELS="$(cf GET "/accounts/${ACCOUNT_ID}/cfd_tunnel?is_deleted=false")"
printf '%s' "$TUNNELS" | parse '
import json,sys
data=json.load(sys.stdin)
assert data.get("success"), data
for t in data.get("result", []):
    print("{}\t{}\t{}".format(t.get("name"), t.get("id"), t.get("status")))
'

TUNNEL_ID="${CF_TUNNEL_ID_LION:-}"
if [[ -z "$TUNNEL_ID" ]]; then
  TUNNEL_ID="$(printf '%s' "$TUNNELS" | parse '
import json,sys
data=json.load(sys.stdin)
preferred={"lion", "cloudflared-lion", "LION"}
for t in data.get("result", []):
    if t.get("name") in preferred:
        print(t["id"])
        raise SystemExit
if len(data.get("result", [])) == 1:
    print(data["result"][0]["id"])
')"
fi
if [[ -z "$TUNNEL_ID" ]]; then
  echo "could not determine LION tunnel id" >&2
  exit 1
fi
echo "tunnel_id length=${#TUNNEL_ID}"

CFG="$(cf GET "/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations")"
printf '%s' "$CFG" | parse '
import json,sys
data=json.load(sys.stdin)
assert data.get("success"), data
ingress=(data.get("result", {}).get("config", {}) or {}).get("ingress", [])
print("ingress rules", len(ingress))
for rule in ingress:
    print("{}\t{}".format(rule.get("hostname", "(catch-all)"), rule.get("service")))
'

HAS_HOST="$(printf '%s' "$CFG" | parse '
import json,sys
data=json.load(sys.stdin)
ingress=(data.get("result", {}).get("config", {}) or {}).get("ingress", [])
print("yes" if any(r.get("hostname")=="stagecoach.cybersphere.com.br" for r in ingress) else "no")
')"

NEW_CFG="$(printf '%s' "$CFG" | parse '
import json,sys
data=json.load(sys.stdin)
config=(data.get("result", {}) or {}).get("config") or {}
ingress=list(config.get("ingress") or [])
hostname="stagecoach.cybersphere.com.br"
origin="http://127.0.0.1:3107"
if not any(r.get("hostname")==hostname for r in ingress):
    catch=[]
    kept=[]
    for rule in ingress:
        if not rule.get("hostname"):
            catch.append(rule)
        else:
            kept.append(rule)
    kept.append({"hostname": hostname, "service": origin, "originRequest": {"httpHostHeader": hostname}})
    if not catch:
        catch=[{"service": "http_status:404"}]
    config["ingress"]=kept+catch
print(json.dumps({"config": config}))
')"

echo
echo "== tunnel hostname =="
if [[ "$HAS_HOST" == "yes" ]]; then
  echo "already present"
elif [[ "$APPLY" -eq 1 ]]; then
  echo "adding public hostname to tunnel (preserving existing ingress)"
  cf PUT "/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations" --data "$NEW_CFG" \
    | parse 'import json,sys; d=json.load(sys.stdin); assert d.get("success"), d; print("tunnel config updated")'
else
  echo "dry-run: would add $HOSTNAME -> $ORIGIN on tunnel"
fi

echo
echo "== DNS =="
RECORDS="$(cf GET "/zones/${ZONE_ID}/dns_records?name=${HOSTNAME}")"
printf '%s' "$RECORDS" | parse '
import json,sys
data=json.load(sys.stdin)
assert data.get("success"), data
print("records", len(data.get("result", [])))
for r in data.get("result", []):
    print(r.get("type"), r.get("name"), r.get("content"), "proxied="+str(r.get("proxied")))
'

RECORD_COUNT="$(printf '%s' "$RECORDS" | parse '
import json,sys
print(len(json.load(sys.stdin).get("result", [])))
')"
DNS_BODY="$(TUNNEL_ID="$TUNNEL_ID" python3 -c 'import json,os; print(json.dumps({
  "type": "CNAME",
  "name": "stagecoach",
  "content": os.environ["TUNNEL_ID"] + ".cfargotunnel.com",
  "ttl": 1,
  "proxied": True,
}))')"

STALE_ID="$(printf '%s' "$RECORDS" | TUNNEL_ID="$TUNNEL_ID" parse '
import json,os,sys
want=os.environ["TUNNEL_ID"] + ".cfargotunnel.com"
for r in json.load(sys.stdin).get("result", []):
    if r.get("type") != "CNAME" or r.get("content") != want or not r.get("proxied"):
        print(r["id"])
        break
')"

if [[ "$RECORD_COUNT" == "0" && "$APPLY" -eq 1 ]]; then
  echo "creating proxied CNAME"
  TUNNEL_ID="$TUNNEL_ID" \
    cf POST "/zones/${ZONE_ID}/dns_records" --data "$DNS_BODY" \
    | parse 'import json,sys; d=json.load(sys.stdin); assert d.get("success"), d; print("dns created")'
elif [[ "$RECORD_COUNT" == "0" ]]; then
  echo "dry-run: would create proxied CNAME stagecoach -> <tunnel>.cfargotunnel.com"
elif [[ -n "$STALE_ID" && "$APPLY" -eq 1 ]]; then
  echo "repointing existing record at the LION tunnel"
  cf PUT "/zones/${ZONE_ID}/dns_records/${STALE_ID}" --data "$DNS_BODY" \
    | parse 'import json,sys; d=json.load(sys.stdin); assert d.get("success"), d; print("dns updated")'
elif [[ -n "$STALE_ID" ]]; then
  echo "dry-run: would repoint existing record to the LION tunnel (proxied CNAME)"
else
  echo "record already points at the LION tunnel"
fi

echo
echo "done. apply=$APPLY"
