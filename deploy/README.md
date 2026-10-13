# Stage Coach production deploy (LION)

Production is **LION** (`LION.local`, lab VLAN), loopback Docker Compose,
Cloudflare Tunnel hostname `stagecoach.cybersphere.com.br`, Access policy
**before** DNS. Deploy from a logged-in session on LION, or from TIGER with
`ssh lion`. The corporate laptop cannot resolve `LION.local` and holds no
lab secrets. `deploy/stagecoach-run.sh` prepends `~/.orbstack/bin` because
that is where LION's Docker CLI lives and launchd does not inherit it.

## Inventory (cyberlabs repo)

Add before the first LaunchAgent:

```yaml
# architecture/services.yaml
- id: stagecoach
  host: lion
  kind: webapp
  port: 3107
  bind: 127.0.0.1
  supervisor: launchagent
  label: com.cyberlabs.stagecoach
  health: /
```

Also declare the Compose containers (web, api, worker, postgres, redis) so
`docker ps` does not report them as undeclared. OrbStack on LION is otherwise
documented as Vaultwarden-only.

Dataflow: internet → `cloudflared-lion` → `http://127.0.0.1:3107`. The API is
not published on the host (Splunk owns `:8000`).

## Keychain (GUI session on LION)

Create these items; do not put values in git:

- `cyberlabs-POSTGRES_PASSWORD`
- `cyberlabs-AUTH_SECRET` (≥ 32 characters)
- `cyberlabs-PRIVATE_BETA_EMAIL`
- `cyberlabs-CF_API_TOKEN` (Cloudflare API token used only by the edge setup helper)
- `cyberlabs-splunk-rum-token` (optional public browser RUM token; omitted means RUM stays off)

The web, API, and worker containers export OTLP to `http://host.docker.internal:4318` with `service.name=stagecoach`. The host collector on loopback `:4317`/`:4318` is the only place the Splunk ingest token lives.

Login Keychain does not unlock over SSH. First secret write and `launchctl`
install happen in the logged-in GUI session.

## Cloudflare

1. Create Access application + allow policy for `stagecoach.cybersphere.com.br`.
2. Then add the `lion` tunnel public hostname pointing at `http://127.0.0.1:3107`.
3. Catch-all 404 until both exist.

## Install

One command, in a logged-in Terminal on LION (not SSH):

```bash
curl -fsSL https://raw.githubusercontent.com/clebervisconti/stagecoach/main/deploy/lion-bootstrap.sh -o /tmp/lion-bootstrap.sh
bash /tmp/lion-bootstrap.sh
```

It checks that it is on LION in the GUI session with OrbStack running,
clones or updates `~/cyberlabs/apps/stagecoach`, creates any missing
Keychain item through a hidden prompt (generated values go via the
clipboard, which is cleared afterwards), installs the LaunchAgent, waits for
loopback health, confirms 3107 is loopback-only, then runs the Cloudflare
helper as a dry run and applies it only after you confirm. The helper
refuses to touch the tunnel or DNS unless the Access app has an allow
policy, and repoints an existing DNS record if it targets another tunnel.

Manual equivalent:

```bash
# on LION, after cloning this repo to ~/cyberlabs/apps/stagecoach
install -m 0755 deploy/stagecoach-run.sh ~/cyberlabs/hosts/lion/stagecoach-run.sh
install -m 0644 deploy/com.cyberlabs.stagecoach.plist ~/Library/LaunchAgents/com.cyberlabs.stagecoach.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cyberlabs.stagecoach.plist
curl -fsS http://127.0.0.1:3107/api/health
```

Cloudflare (Access first, DNS last):

```bash
# discovery
bash deploy/cloudflare-private-beta.sh
# mutate after Access payload looks right
bash deploy/cloudflare-private-beta.sh --apply
bash scripts/verify-live.sh
```

Reload after `main` updates:

```bash
launchctl stop com.cyberlabs.stagecoach
docker compose -f docker-compose.prod.yml down
launchctl start com.cyberlabs.stagecoach
```

Do not `launchctl kickstart -k` while Compose is the foreground process.

## Constraints recorded here

- This product currently lives in a **public** GitHub repo. Homelab policy prefers a private repo; keep Cloudflare Access on until that changes.
- The worker runs CPU ASR (`ASR_MODEL=tiny`) on LION. Larger models belong on TIGER or a remote API.
- Alignment (#93) and diarization (#94) are deferred; the private-beta report marks Q&A/video/content categories N/A.
