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
not published on the host (Splunk owns `:8000`). Postgres `:5432` is also
taken.

## Lab overlay (`infra/compose.lion.yaml`)

Compose **merges** `ports` lists. `ports: []` does not unpublish the base
file's `:8000` / `:5432`. The overlay uses `!reset []` and `!override` so
the merged config publishes only:

- `127.0.0.1:8870` → web (`node server.js` standalone, no source mount, no `npm run dev`)
- `127.0.0.1:6380` → Redis
- `127.0.0.1:9010` → MinIO

Postgres, API, and Mailpit stay unpublished. Confirm with:

```bash
make lion-config
# or:
docker compose -f docker-compose.yml -f infra/compose.lion.yaml \
  --profile web --profile minio --profile workers config --format json
```

Build images on LION (OrbStack / linux/arm64) from a checkout with `.env`:

```bash
make lion-build
make lion-up
```

The `make lion-*` targets take the same knobs the lab actually uses. None
of these files belong in git if they hold secrets:

| Variable | Default | Purpose |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `stagecoach` | Compose project (`-p`) so lab containers do not collide with another stack |
| `ENV_FILE` | `.env` | Passed as `--env-file` when the file exists. Create it on LION; do not commit it |
| `LION_OVERRIDE` | empty | Extra compose file (loopback / local ports). Example: `infra/compose.lion.local.yaml` on the host only |
| `LION_SERVICES` | `postgres redis minio api worker web mailpit` | Services started by `lion-up`. **worker-beat is omitted** |

```bash
make lion-up \
  COMPOSE_PROJECT_NAME=stagecoach \
  ENV_FILE=.env \
  LION_OVERRIDE=infra/compose.lion.local.yaml
```

`worker-beat` is on the `lion-beat` profile, not `workers`. Do not start it
on LION unless you pass `--profile lion-beat`.

The API overlay command is production uvicorn (no `--reload`). The worker
image is a multi-stage build: `g++` / `make` / `ninja` stay in the build
stage so `praat-parselmouth` can compile on arm64. Torch is `2.4.1+cpu`
from the PyTorch CPU index on amd64 and `2.4.1` from PyPI on arm64.
YuNet, Silero VAD, MediaPipe `.task` files, faster-whisper `small`, and
NLTK `punkt` / `punkt_tab` are baked into `/models` at build time.

MinIO is `cgr.dev/chainguard/minio:latest-dev` pinned by image-index digest
(quay.io/minio/minio returns 401; the image is multi-arch and AGPL). The
healthcheck uses `wget` against `/minio/health/live`.

Production (`docker-compose.prod.yml` / LaunchAgent) still binds web on
`127.0.0.1:3107` and also runs the standalone Next server.

Public URLs come from `STAGECOACH_PUBLIC_URL`. The lab overlay
(`infra/compose.lion.yaml`) copies that value into `AUTH_URL`,
`NEXTAUTH_URL`, and the API's public URL. The default, when the variable
is unset, is `http://127.0.0.1:8870`. `AUTH_URL` is the public origin, not
a secret. Auth.js returns 500 UntrustedHost on `/api/auth/*` until it is
set. The overlay also sets `AUTH_TRUST_HOST=true` so a forwarded host from
the tunnel is accepted. On LION production set the Cloudflare origin in
`.env` — never commit a password or a personal address:

```bash
STAGECOACH_PUBLIC_URL=https://stagecoach.cybersphere.com.br
```

## Keychain (GUI session on LION)

Create these items; do not put values in git:

- `cyberlabs-POSTGRES_PASSWORD`
- `cyberlabs-AUTH_SECRET` (≥ 32 characters)
- `cyberlabs-PRIVATE_BETA_EMAIL` — only the Cloudflare Access allow policy, until Access is removed. The app does not read it.
- Cloudflare: the existing lab token `cyberlabs-cloudflare-api` is used first; `cyberlabs-CF_API_TOKEN` is only a fallback
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

## App auth cutover

Migration `012_roles_sessions` runs when the API container starts. Both `docker-compose.prod.yml` and the LION overlay `infra/compose.lion.yaml` run `alembic upgrade head` before uvicorn. A restart at the current head is a no-op. The migration adds roles and session versions. It does not insert an account. Existing users become `member`. `ONLINE_MODES_ALLOWED_EMAILS`, `PRIVATE_BETA_EMAIL`, and `STAGECOACH_ADMIN_EMAILS` no longer grant access. Online modes stay off for every user until an admin turns on that user's `online_modes` flag at `/admin/users` (Turn online modes on). `ONLINE_MODES_ENABLED` must still be on for the whole service. An admin account does not get the flag automatically.

Do this in order. Leave Cloudflare Access in place until the last step.

1. Deploy this release and wait until the API is healthy (the migration has run).
2. On LION, create the first admin. The values stay in the shell. Do not write them into git, `.env`, or the LaunchAgent:

```bash
read -r BOOTSTRAP_ADMIN_EMAIL
read -rs BOOTSTRAP_ADMIN_TEMP_PASSWORD
export BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_TEMP_PASSWORD
docker compose -f docker-compose.prod.yml exec -T \
  -e BOOTSTRAP_ADMIN_EMAIL -e BOOTSTRAP_ADMIN_TEMP_PASSWORD \
  api python -m app.bootstrap_admin
unset BOOTSTRAP_ADMIN_TEMP_PASSWORD
```

On the LION host that runs the lab stack through `sc.sh`, use that wrapper instead of `docker-compose.prod.yml`:

```bash
read -r BOOTSTRAP_ADMIN_EMAIL
read -rs BOOTSTRAP_ADMIN_TEMP_PASSWORD
export BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_TEMP_PASSWORD
~/Cyberlabs/services/stagecoach-lion/sc.sh exec -T -e BOOTSTRAP_ADMIN_EMAIL -e BOOTSTRAP_ADMIN_TEMP_PASSWORD api python -m app.bootstrap_admin
unset BOOTSTRAP_ADMIN_TEMP_PASSWORD
```

`created` or `updated` means the temporary password must be changed at first sign-in. `present` means an admin with a password was left alone. Run it again only to confirm; it will not reset that password.

3. Sign in at the app with that email and the temporary password. Set a new password (at least 10 characters, not a common breached password). Open Users and confirm you can see the account. Online modes stay off until you turn that user's flag on there. Open a normal session page.
4. Only then remove the Cloudflare Access application. `deploy/cloudflare-private-beta.sh` stays in the repo until that change is done on the zone. The app does not read `Cf-Access-Jwt-Assertion`.

Forgot password does not send email. An admin uses Force password reset on Users and reads the temporary password once.

## Recording uploads (ADR-085)

Cloudflare rejects a proxied body over 100 MB on Free and Pro (200 MB on Business) with HTTP 413. The browser sends 8 MiB chunks to `PUT /api/stagecoach/sessions/{id}/uploads/{upload_id}/chunks/{n}` and resumes after a drop. Do not raise the zone plan for this. Do not turn the hostname DNS-only to make a single POST fit.

On deploy:

- Redeploy web and API. The API command already runs `alembic upgrade head`. Migration 013 changes `media_assets.bytes` from integer to bigint so a file at the 2 GiB limit can be stored.
- `MAX_UPLOAD_BYTES` defaults to `2147483648`. If the host environment still exports `83886080`, the API ignores that lower value and logs it. Unset it when convenient so the warning goes away.
- The media volume holds the chunks and the assembled file at the same time. A 2 GiB upload needs about 4 GiB free until the parts are deleted.
- No new secret.

## Constraints recorded here

- This product currently lives in a **public** GitHub repo. Do not commit emails, passwords, or personal data. Cloudflare Access can come off only after the app-auth cutover above.
- The worker runs CPU ASR (`ASR_MODEL=tiny`) on LION. Larger models belong on TIGER. Moving ASR is an owner decision; do not point LION at a remote ASR API until that contract exists.
- The upload job runs content analysis before final scoring. If the local model on TIGER is down, categories 1–7 stay N/A. Video categories score only when `video_analysis` consent is on. Q&A stays N/A unless the session includes a Q&A segment; diarization still needs `HF_TOKEN` and is not on the live job.
- WhisperX alignment is implemented and not called by `tasks.run_mvp_analysis`.
- Production mail stays on the console stand-in until `RESEND_API_KEY`, `STAGECOACH_EMAIL_FROM`, and the domain DNS in `docs/email.md` are set by the owner.
- Sign in with Apple stays disabled until `APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, and `APPLE_PRIVATE_KEY` are set. Email and password work without Apple. Cloudflare Access is not the app login; remove it only after the cutover above.
- `docs/PRIVACY.md` is an engineering draft. Counsel reviews it before a public launch. Envelope encryption uses a local key; KMS is an owner decision.
- Live UAT in `tests/uat/mvp-flow.md` is still a manual pass against the running host. It was not executed as part of the 2026-10-17 wiring change.
