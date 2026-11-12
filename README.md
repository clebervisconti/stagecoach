# Stage Coach

An evidence-based presentation coaching platform that analyzes recorded presentations (video or audio) and helps speakers improve through research-grounded feedback.

## Project Status

In-tree product `0.4.0`: upload → analysis (audio, consented video, slides, content coach) → report, plus talk-prep (`/prep`), trends, and account export. Sign-in is the app's own email and password or Sign in with Apple (ADR-083). Cloudflare Access may still sit in front of `https://stagecoach.cybersphere.com.br` until the cutover in `deploy/README.md`. The app does not trust Access headers. Speech recognition stays on the worker (`ASR_BACKEND=local`). Production compose still defaults `ASR_MODEL` to `tiny` until the owner cuts a release. An HTTP client exists and is off (ADR-091).

Recordings upload in 8 MiB chunks (ADR-085), so a file up to 2 GiB can pass Cloudflare's proxied body cap on the LION hostname. A dropped chunk retries, and Try again resumes. "File too large" is only for a file over 2 GiB.

Production: LION loopback `:3107`, LaunchAgent `com.cyberlabs.stagecoach`. See `deploy/README.md`.

LION is Apple silicon / OrbStack / **linux/arm64**. The worker image builds from this tree with no local override: torch 2.4.1 from the CPU index on amd64 and from PyPI on arm64; YuNet, Silero VAD, MediaPipe `.task` files, and faster-whisper `small` are baked into `/models`. Lab ports are `infra/compose.lion.yaml` (`make lion-build` / `make lion-up`, with `COMPOSE_PROJECT_NAME` / `ENV_FILE` / `LION_OVERRIDE`) — only loopback 8870 / 6380 / 9010. Do not bind host `:8000` or `:5432`. `worker-beat` is off by default on LION.

## Quick Links

- [Full Specification](docs/SPEC.md) - Complete product and technical specification
- [Architecture Decisions](docs/DECISIONS.md) - ADRs for key technical choices
- [Research Sources](docs/research/sources.md) - Verified research citations (in-app: `/research`, `/research/myths`, `/config/scoring/1.0.0`, `/config/scoring/1.1.0`)
- [Validation Plan](docs/VALIDATION.md) - Methodology and validation results

## Architecture Overview

Stage Coach is a monorepo containing:

- **apps/web** - Next.js web application (React, TypeScript, Tailwind)
- **services/api** - FastAPI REST API (Python 3.11+)
- **services/analysis** - Celery workers for media analysis pipeline
- **packages/scoring-config** - Versioned scoring weights and curves
- **packages/schemas** - JSON schemas and type definitions
- **packages/scoring** - Scoring engine implementation
- **packages/lexicons** - Language-specific lexicons (fillers, hedges, etc.)

## Technology Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, React, Tailwind CSS, shadcn/ui
- **API**: Python 3.11+, FastAPI, pydantic v2
- **Workers**: Celery + Redis queue
- **Database**: PostgreSQL 16 with SQLAlchemy 2
- **Storage**: S3-compatible object storage (MinIO locally)
- **Auth**: email + password (argon2id) and Sign in with Apple. Roles are `admin`, `member`, and `viewer` (ADR-083, ADR-084). The first admin is created on the server with `python -m app.bootstrap_admin`, not from git. See `deploy/README.md`.
- **Analysis**: faster-whisper, MediaPipe, parselmouth, LLM providers

## Development Setup

### Prerequisites

- Docker and Docker Compose
- Node.js 22+ and npm
- Python 3.11+
- Make

### Quick Start

```bash
# Clone and install dependencies
git clone https://github.com/clebervisconti/stagecoach.git
cd stagecoach
make install

# Start development environment
make dev

# Run tests
make test

# View logs
make logs
```

The application will be available at:
- Web app: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

### Public repository

Do not commit personal emails, local usernames, home paths, or credential-looking strings.

- Placeholders: `YOUR_USERNAME`, `example@example.com`, `/Users/YOUR_USERNAME/...`.
- A test fixture that needs a password uses a clearly fake value (`password` or `REDACTED`).
- `.env.example` stays empty or interpolated. Do not put a placeholder password that looks real.
- Use your GitHub noreply address as the git author. Do not use a personal mailbox.
- A URL may include userinfo only when the password is `password`, `REDACTED`, the same as the username, or an interpolated variable such as `${POSTGRES_PASSWORD}`.

Before pushing, run `python3 scripts/scan_public_tree.py`. That script reads tracked files in the current tree and does not read git history. CI runs the same script, then `gitleaks detect --no-git --redact --config .gitleaks.toml` with gitleaks 8.24.3 (the version that reads this repo's `[allowlist]` table). Install that release locally if you want the generic scan as well: https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3

## Project Principles

1. **Research-grounded**: Every scoring claim traces to published research or is labeled as heuristic
2. **Privacy by default**: Encryption at rest, user-controlled retention, GDPR/LGPD compliance
3. **Transparent scoring**: All weights, curves, and thresholds are versioned and auditable
4. **Responsible AI**: No emotion inference; expression analysis is opt-in and descriptive only
5. **Test-first**: Unit tests for metric functions, golden-file tests for pipeline stages
6. **Reproducible**: Fixed config versions ensure old reports can be regenerated

## Documentation

- **Setup**: See [docs/SETUP.md](docs/SETUP.md) for detailed installation instructions
- **Architecture**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- **API**: See [docs/API.md](docs/API.md) or http://localhost:8000/docs for API reference
- **Contributing**: See [Public repository](#public-repository) for what must not be committed
- **Privacy**: See [docs/PRIVACY.md](docs/PRIVACY.md) for data handling and compliance

## Phase Roadmap

Matches `product/ROADMAP.md` and `product/BACKLOG.md`. `ONLINE_MODES_ENABLED` stays off until O4. Do not start O4.

- ✅ **Phase 0**: Foundations - monorepo, DB, config, scoring engine
- ✅ **Phase 1**: Audio + text report - ASR, fusion scoring, evidence-linked report, delete
- ✅ **Phase 2**: Video + slides - consents, CPU MediaPipe, categories 8 and 12–15, timeline, Body and Slides tabs, PDF, retention, local LLM default
- ✅ **Phase 3 (0.4, in tree)**: Talk-prep generators on the live job, objectives panel, trends, goals, personal-baseline badge after 3 sessions, account export/deletion
- ✅ **Phase O0 (in tree)**: Online-session foundations — scoring 1.1.0, YuNet, migration 011, synthetic fixtures. Flag off. See `docs/online-sessions/SPEC.md`.
- ✅ **Phase O1 (in tree)**: Walking skeleton — wizard at `/sessions/new`, `tasks.prepare_session`, read-only layout review, production quality, `na_code`, online report. Shown only when the service flag and that user's `online_modes` flag are both on (ADR-084). The linux/arm64 worker image, baked YuNet/Silero/MediaPipe/faster-whisper-small, the composite face, and espeak-ng speech are required for the LION real stack.
- ✅ **Phase O2 (in tree)**: Editable layout, analysis-window trim, re-analyse without a second transcript when the window is unchanged, layout-review preference (hidden until online modes are on for that user). Flag stays off.
- ✅ **Phase O3 (in tree)**: Screen measurement (E3-1–E3-4), scoring for screen flow and online engagement, Screen & flow tab, text-only `online_flow_v1`, factual-correctness line on prompts (E3-5–E3-8). On-camera presence is not started. Flag stays off until O4.
- 📅 **Phase O4–O6**: Not started. Camera presence, two-track upload, and link ingest wait. YouTube and Vimeo stay off (OD-2).
- 📅 **1.0**: Licensed-speech validation, ASR off the worker's `tiny` default, alignment on the live job, and the owner gates in `deploy/README.md`
- 📅 **Phase 4** (v2): Practice loop - in-browser recording, live feedback, drills
- 📅 **Phase 5** (v3): Teams - organizations, coaches, cohort analytics, benchmarks

Still open before a 1.0 cut: licensed-speech validation, WhisperX alignment and diarization on the live job, moving originals to object storage (ADR-003; chunked upload to the media volume is ADR-085), running speech recognition off this worker, and the owner gates in `deploy/README.md` (Resend DNS, Apple secrets, counsel review of `docs/PRIVACY.md`, KMS versus the local envelope key, live UAT). `ASR_BACKEND` stays `local`. Do not set it to `http` or point it at a host until that decision is made (ADR-091).

## Research Foundation

Stage Coach is built on peer-reviewed research in presentation science, speech prosody, multimodal communication, and instructional design. Every evaluation category references specific studies, and all claims are traceable to published sources or explicitly labeled as heuristic.

Key research areas:
- **Message & Structure**: Minto Pyramid Principle, Duarte's Sparkline, Mayer's multimedia learning principles
- **Voice & Prosody**: Pitch variation quotient (Hincks), charisma acoustics (Niebuhr et al.), disfluency effects (Laske & DiGennaro Reed)
- **Nonverbal**: Gesture systems (McNeill), multimodal assessment (Wörtwein et al., Chen et al.)
- **Fair AI**: ASR bias research (Koenecke et al.), responsible affect analysis guidelines

See [docs/research/sources.md](docs/research/sources.md) for the complete bibliography.

## License

MIT License - see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Stage Coach contributors

## Contact

- **Issues**: https://github.com/clebervisconti/stagecoach/issues
- **Discussions**: https://github.com/clebervisconti/stagecoach/discussions

---

Built with rigor, transparency, and respect for privacy.
