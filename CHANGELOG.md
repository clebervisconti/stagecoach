# Changelog

All notable changes to Stage Coach will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 2: Video, slides, full report, PDF (In Progress)

##### Added - Category 13 audience-facing / gaze proxies (issue #41)
- All `ec_*` scoring.yaml metrics from head yaw/pitch and MediaPipe `eyeLook*` blendshapes
- To-camera vs stage thresholds (H); wide shots cap confidence at 0.6 and disable eye-gaze
- UI wording is "audience-facing time (head orientation)", not eye contact; L2CS-Net is not used
- Audio-only, screen recordings, missing faces, and accessibility opt-out stay N/A

##### Added - Category 12 gestures & body + accessibility profile (issue #40)
- All `gb_*` scoring.yaml metrics from pose trajectories and vision events (`gb_gesture_speech_sync` weight 0)
- Hands-visible < 40% → hand-based metrics N/A; webcam framing caps confidence at 0.6; audio-only is N/A
- Accessibility profile (seated/wheelchair, limited mobility, one-handed, prefers_no_video_metrics) disables or adjusts metrics; never inferred
- Unit tests on synthetic trajectories; fusion scores only when `gesture_metrics.json` exists

##### Added - Category 14 facial expressiveness signals, opt-in (issue #42, D8)
- `facial_affect` is scored only when `expression_analysis` is granted (off by default)
- Metrics from MediaPipe blendshapes: smile presence, expressivity index, expression variety
- Incongruence flags are low-confidence observations from content cues overlapping smile/flat-face events
- Forbidden-terms tests cover UI, consent policy, and generated report/expression JSON (en and pt-BR)
- No SER models; no emotion labels

##### Added - Vision events, quality JSON, camera-setup check (issue #39)
- Timestamped `vision_events.json`: gesture strokes, self-adaptors, crossed arms, notes-down, screen turns, locomotion; smile and flat-face only with `expression_analysis`
- `vision_quality.json`: visibility ratios, pixel sizes, luma, camera motion, occlusion, declared vs detected camera setup
- Setup mismatch writes a warning and scales event thresholds; worker receives `camera_setup` from the session
- No emotion labels; synthetic fixtures only

##### Added - Vision stage: MediaPipe pose/hands/face (issue #38)
- CPU-only MediaPipe Tasks VIDEO mode: pose every 15 fps frame, face and hands at 10 fps
- Primary-person IoU tracking, One-Euro then Savitzky-Golay smoothing
- Encrypted `pose.parquet` / `face.parquet` per-second aggregates; raw landmarks discarded unless `keep_detailed_tracking`
- Model SHAs and Apache-2.0 evidence in `models/model_registry.json` and `model_registry` table
- OpenFace is not a dependency; no emotion labels in artifacts

##### Added - Consent UI and `/me/consents` (issue #37)
- `GET /me/consents` and `POST /me/consents` with append-only rows, policy SHA-256, and revocation
- Separate toggles for `video_analysis`, `expression_analysis` (off by default), and `keep_detailed_tracking` in en and pt-BR
- Pipeline gate: no vision processing without `video_analysis`; no facial metrics without `expression_analysis`; raw landmarks only with `keep_detailed_tracking`
- Session upload snapshots current consents into `consents.json` for the job

## [0.2.0] - 2026-10-10

### Added
- Private-beta upload → background analysis → partial report → delete flow
- Production Compose stack on LION (`127.0.0.1:3107`) behind Cloudflare Access
- Health endpoint `GET /api/health` for the web BFF

### Phase 1: Audio + text MVP report (In Progress)

##### Added - Phase 1 exit e2e, CPU bench, and filler disambiguation (issue #36)
- Playwright e2e covers upload → progress → report → delete (en) and the same path in pt-BR
- Transcript tab shows né/tipo/então (and like/so) heuristic readings; only confirmed fillers count toward `fl_filler_words_per_min`
- `scripts/bench_phase1_cpu.py` times ingest → ASR → audio-features → fusion → report on a 10-minute synthetic clip
- Observed wall times are recorded in `docs/demos/phase-1.md` (unmeasured claims are labelled as such)

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

##### Added - Session hard delete + audit (issue #34)
- `DELETE /sessions/{id}` removes `MEDIA_ROOT/{session_id}` files, the object-store prefix when MinIO is reachable, and CASCADE DB rows (session, assets, jobs, steps, scores, evidence, insights, transcripts)
- Writes `audit_log` `session.delete` with object count and row counts only (no title, transcript, quote, or storage URIs)
- Writes `deletion_requests` proof with remaining counts; HTTP 500 if anything is left
- Search index is not deployed in Phase 1, so there are no index entries to remove
- Unit tests cover leftover files, prefix isolation, and content-key rejection; smoke plants files under the session dir (never `smoke-fixture`) and asserts 204 then 404

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
