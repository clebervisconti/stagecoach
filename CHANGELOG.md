# Changelog

All notable changes to Stage Coach will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-10

### Added
- Private-beta upload → background analysis → partial report → delete flow
- Production Compose stack on LION (`127.0.0.1:3107`) behind Cloudflare Access
- Health endpoint `GET /api/health` for the web BFF

### Phase 1: Audio + text MVP report (In Progress)

##### Added - Golden fixtures and metric validation start (issue #35)
- Three synthetic licensed clips (`en_clean`, `ptbr_clean`, `noisy_low_snr`); no personal recordings
- `scripts/process_local.py --golden` compares fusion output with ±2 score points and ±5% metrics
- Noisy fixture (SNR 10 dB, confidence 0.3) is Low and excluded from overall
- `docs/VALIDATION.md` logs fillers, WPM, and pauses on ≥ 20 min annotated timestamps per language (en, pt-BR)

##### Added - Fusion scoring and report (issue #30)
- `fusion_scoring` stage maps existing `metrics.json` / `content.json` / transcript / audio features onto scoring-config v1.0.0
- Missing inputs mark a category N/A; video categories 8 and 12–14 are N/A with reasons
- `report` stage writes facts-only coach text, attaches drills via `drill_rules.yaml`, and writes `report.json`
- Reversible Alembic migration `003_result_tables` for transcripts, metric_values, category_scores, overall_scores, evidence_items, insights
- Provenance records scoring-config 1.0.0 and model versions
- Smoke fixture now produces `analysis_result.json` and `report.json`

##### Added - Player, transcript highlights, Voice tab (issue #33)
- Evidence chips seek to `t_start − 2 s` (clamped at 0)
- Keyboard player: Space, ←/→ 5 s, J/L evidence markers
- Transcript tab: speaker labels, click-to-seek, highlight toggles, filler breakdown, TXT/SRT/VTT export
- Voice tab: pace with context band, pitch, loudness/energy, pause histogram, filler-per-section with 5/min and 12/min lines
- Unavailable series stay unavailable (not plotted as zero)

##### Added - Report v1 UI (issue #32)
- Session report page reads `GET /sessions/{id}/report` (analysis_result view model)
- Summary card: overall as `71 ± 4 · Strong`, Partial badge, coverage, config-weight tooltip
- SVG radar of 6 pillars with N/A gaps (never plotted as 0) and a table alternative
- Key metrics strip with info dialogs (definition, source/heuristic, confidence)
- Top-3 opportunities, strengths, weaknesses, and category cards (score, level, confidence chip, why-this-score, counterfactual, source keys, N/A reason)
- en and pt-BR strings; no emotion-inference terms
- Node tests for the view model plus a forbidden-terms scan of UI strings

##### Added - Report API (issue #31)
- `GET /sessions/{id}/report`, `/analysis`, `/transcript`, `/series/{name}`, `/media`, `/media/playback`
- `POST /evidence/{id}/dispute` stores a note and sets `user_disputed`
- Ownership checks: a user can read only their own sessions
- Playback URL is HMAC-signed and expires in 15 minutes
- Redis token-bucket rate limits on `/api/v1` (per user and per IP)
- Smoke: `GET /report` returns the synthetic fixture `report.json`

##### Added - Audio-features stage
- `audio_features` stage (issue #24, SPEC §6.4) writing `prosody.parquet` (10 ms), `pauses.json`, `syllables.json`, `audio_metrics.json`
- Two-pass Praat F0 with speaker-adaptive floor/ceiling and octave-jump removal
- PVQ and semitone-relative pitch (Hincks [S24]); de Jong & Wempe syllable nuclei [S25]
- Pause classification (boundary vs mid-sentence) from ASR punctuation
- SNR estimate and heuristic music/noise flags that feed confidence
- ADR-013: parselmouth GPL is server-side only
- Unit tests: sine / chirp → F0 and PVQ; pause, SNR, and artifact checks

### Phase 0: Foundations (In Progress)

#### [0.1.0] - 2026-10-09

##### Added - Scoring Configuration and Engine
- Complete scoring configuration v1.0.0 per SPEC §4
  - 17 categories across 6 pillars
  - 60+ sub-metrics with research-grounded curves
  - 6 context weight profiles (keynote, breakout, exec briefing, sales, virtual, class)
  - All metrics labeled as research-based (with source keys) or heuristic
- Python scoring engine (`packages/scoring/`)
  - Piecewise-linear curve interpolation
  - LLM level → score mapping
  - Confidence-based inclusion factors
  - Category and overall score aggregation
  - N/A handling and gates
  - Opportunity ranking by impact
- Comprehensive unit tests (curves, engine, config validation, schema validation)
- Research sources bibliography (docs/research/sources.md) with 56 verified references

**Owner Review & Approval**: Product owner reviewed and approved the scoring configuration and scoring engine on **2026-10-08** per §12.1 step 8. This unblocks Phase 1 pipeline development.

##### Added - Database and Type Generation
- Alembic database migration framework
- Baseline migration (001) with Phase 0 schema per §7.3:
  - `users` - user accounts with accessibility preferences
  - `consents` - append-only consent tracking
  - `sessions` - recording sessions with context
  - `media_assets` - media files with retention policies
  - `analysis_jobs` - pipeline job tracking
  - `job_steps` - stage execution records
  - `scoring_configs` - immutable versioned configs
  - PostgreSQL extensions: pgcrypto, citext, uuid-ossp
- SQLAlchemy 2.0 models for all tables
- Type generation from JSON schemas to pydantic v2 models
- CI check for stale generated code

##### Added - Infrastructure
- Monorepo structure per §7.2
- Docker Compose with Postgres 16, Redis 7, MinIO, Mailpit
- Makefile with dev, test, lint, migrate, generate-types commands
- GitHub Actions CI: lint, type check, tests, config validation, secret scan, compose smoke test
- Architecture Decision Records (ADR-001 through ADR-006)

##### Added - Next.js Web Application
- Next.js 14 with App Router and TypeScript strict mode
- Tailwind CSS with shadcn/ui theming
- next-intl for bilingual support (en, pt-BR)
- Auth.js v5 with Nodemailer SMTP provider
- Marketing landing page + app shell (sessions/trends/prep/settings pages)
- Strict Content Security Policy per §10.7

##### Added - FastAPI Backend
- FastAPI with pydantic v2
- JWT verification for Auth.js tokens (HS256)
- GET/PATCH `/api/v1/me` endpoints
- POST `/api/v1/sessions` endpoint (returns session + tus_url)
- RFC 9457 problem+json error responses

##### Added - Full Dev Stack
- Celery worker skeleton with cpu/gpu/llm queue declarations
- TUS server for resumable uploads (tusd)
- Database seed scripts (demo user, scoring config)
- Updated `make dev` workflow

##### Added - Privacy Baseline
- docs/PRIVACY.md stub per §10
- Gitleaks secret scanning in CI
- Structured logging (no PII/media)

## Version History

- **0.1.0** - Phase 0 Foundations (Complete)
  - Issues #1-#16: Monorepo, scoring engine, database, type generation, web app, auth, dev stack
  
---

## References

- SPEC: docs/SPEC.md
- ADRs: docs/DECISIONS.md
- Acceptance Criteria: §12 of SPEC.md
