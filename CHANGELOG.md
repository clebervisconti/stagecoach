# Changelog

All notable changes to Stage Coach will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 3: Talk-prep coach + objectives + trends (In Progress)

##### Fixed - LION deploy on Apple Silicon (OrbStack / arm64)
- `infra/compose.lion.yaml` uses `!reset` / `!override` so only `127.0.0.1:8870`, `6380`, and `9010` are published (`ports: []` does not clear the base list)
- MinIO image is `cgr.dev/chainguard/minio` pinned by multi-arch digest (quay.io/minio/minio returns 401)
- LION and production web build Next.js and run `next start` (no source mount, no `npm run dev`)
- Worker image installs arch-conditional CPU torch so linux/arm64 and amd64 both build; CI buildx checks the arm64 torch stage
- API LION command is production uvicorn (no `--reload`); `make lion-build` builds the images

##### Changed - Default LLM is local LM Studio / Qwen (owner decision 2026-10-16)
- Default provider is `local`; model `qwen/qwen3.8-27b`; base URL from `LOCAL_LLM_BASE_URL`
- No API key for the default. `XAI_API_KEY` is optional; the app boots without it
- xAI/Grok stays selectable in Settings and warns that data leaves the machine
- `infra/compose.lion.yaml` publishes only `127.0.0.1:8870` plus Redis `6380` and MinIO `9010`

##### Added - Zip data export and 7-day account deletion (issue #67)
- `POST /me/export` zip: sessions, scores, evidence, transcripts, plans, consents + 24 h signed media links
- `DELETE /me` starts a 7-day grace; `POST /admin/account-deletions/finalize` hard-deletes when due
- Confirmation email + content-free audit; Settings download / delete / cancel
- Tests use HMAC stand-ins (no live S3 or Resend)

##### Added - Resend transactional email (issue #67 / D10)
- Resend adapter behind `send_email`; console stand-in when `RESEND_API_KEY` is unset
- text + HTML templates for verification and password reset; retry/backoff
- Logs never include bodies or tokens; Cyberlabs DNS steps in `docs/email.md`

##### Added - Plan editor, readiness scores, Markdown/PDF export (issue #61)
- `/prep/{id}` inline edit + regenerate with feedback for every prep section
- Readiness for categories 1–8 and 16–17 from materials; 9–15 N/A until rehearsal
- Top 3 changes; Markdown download and print/PDF page

##### Added - Trends API + dashboard (issue #64)
- `GET /trends` filtered by metric / category / context / language
- Incompatible sessions (other context or scoring-config major) marked not comparable with a reason
- Sparklines, most improved, and needs attention on `/trends`

##### Added - Plan-a-talk form + prep_clarify_v1 (issue #56)
- `/prep` form fields per SPEC §9.1 (en / pt-BR); description capped at 4,000 characters
- `POST /plans/{id}/clarify` runs `prep_clarify_v1` (≤ 5 questions); skip writes explicit assumptions
- Stand-in extractor in tests; live LLM is an optional `generate` hook only

##### Added - talk_plans, goals, objective_scores + plan API (issue #55)
- Reversible Alembic `008_talk_plans`
- `POST/GET/PATCH /plans` and `POST /plans/{id}/regenerate` enqueue `prep_llm`
- User edits and regenerations increment `version`; history stores field names / feedback length only
- Ownership 404; `prep_*` LLM bodies deferred to #56–#62

### Phase 2: Video, slides, full report, PDF (In Progress)

##### Added - Phase 2 exit fixtures and CPU bench (issue #54)
- Stage / to-camera / screen-recording fixtures assert the N/A matrix and non-zero confidence
- CPU fusion-only ratio ≤ 1.5× on the synthetic transcript; vision scripted-frame s/media-minute recorded in ADR-042
- GPU and full-pipeline 20-min P50 are flagged (this CI is CPU-only)

##### Added - Report accessibility WCAG 2.2 AA (issue #53)
- `@axe-core/playwright` on the report (test-only; axe-core is MPL-2.0 and was already a transitive dep)
- Keyboard-only coverage of player, evidence chips, and timeline lanes
- Captions from the transcript (`<track kind="captions">`)
- Color-blind hatch patterns on radar and timeline; `prefers-reduced-motion`

##### Added - Observability: OTel, Prometheus, admin cost (issue #52)
- API and workers start OTel when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (existing Splunk distro)
- Prometheus `GET /metrics` with handler templates only (no PII labels)
- Admin `GET /admin/analysis-costs` gated by `STAGECOACH_ADMIN_EMAILS`
- Error tracking stays `none` until the owner chooses Sentry SaaS, self-hosted, or none — no Sentry SDK

##### Added - In-app References, Myths and limits, scoring config (issue #51)
- `GET /research/sources` lists [S1]–[S56] from `docs/research/sources.md` with stable anchors
- `/research` References page; category cards and metric info link to `#S#`
- `/research/myths` renders SPEC §4.8 (no 7-38-55, no emotion reading, no accent scoring)
- Read-only `/config/scoring/{version}` and `GET /config/scoring/{version}`

##### Added - AI provider settings (owner decision 2026-10-14)
- xAI (Grok) remains the default
- Settings → AI providers: local OpenAI-compatible (LM Studio / Gemma), Anthropic, OpenAI, Gemini, custom URL
- Non-default cloud providers warn that analysis text leaves the machine
- API keys from env / secrets only; never stored in settings or the repo
- Tests use in-memory stand-ins (no live calls)

##### Added - Retention sweeper, lifecycle backstop, envelope encryption (issue #50)
- User retention choices: delete after analysis, 30 days (default), or keep until session delete
- Nightly Celery beat `retention_sweeper` deletes `media_assets` past `retention_until` (time-travel test)
- `audio16k` and the analysis proxy are removed when the job completes
- Derived biometric JSON (`expression_metrics.json`) is SCENC2 envelope AES-GCM; local KEK in dev, KMS left as an owner decision
- Object-storage lifecycle rules live in `infra/object-storage-lifecycle.json` (not applied in CI; minio profile skipped)

##### Added - PDF export via Playwright Chromium (issue #49)
- `POST /sessions/{id}/export/pdf` enqueues a CPU worker job; `GET /exports/{id}` and `/file`
- Print HTML sections follow SPEC §8.9; charts are SVG; keyframes replace video
- Transcript is omitted unless "include transcript" is ticked
- Visual snapshot compares the print view to the web report score and layout

##### Added - Body tab and Slides tab (issue #48)
- Body: gesture heat strip, wrist-space silhouette, events list, sway, yaw histogram, notes-down, opt-in expressivity, data-quality panel
- Slides: filmstrip with dwell, words, title type, Glance level, reading %, facing-screen seconds; click seeks
- Suggested assertion titles appear only from `slides_v1`, labeled AI
- Missing vision or slides stay N/A; no invented scores

##### Added - Video-synced timeline lanes (issue #47)
- Lanes: sections, slides, fillers, long pauses, rushing, monotone, gestures, audience-facing, smiles (opt-in), CLT/story, Q&A
- Toggleable lanes, sprite hover (ingest 5 s / 160px), click-to-seek, two-way playhead
- J/L jump markers in the focused lane; Space and ←/→ stay on the player

##### Added - Partial results and graceful vision degradation (issue #46)
- SSE `partial_ready` events list scored category ids; `done` marks the terminal report
- Audio/text fusion runs before vision so the report page can render live cards while processing
- Vision failure continues the job: categories 12–14 stay N/A with “Vision stage failed…”, never invented scores
- Consent-off and accessibility reasons still take precedence over a failed-vision reason

##### Added - Category 15 energy & presence fusion (issue #45)
- Composite E(t) = mean of z-scores of loudness, PVQ, gesture activity, and expressivity when each exists
- Trajectory is last-third minus first-third; missing modalities stay N/A, never a made-up score
- Not labeled as confidence detection; no SER models
- `ep_confident_language` / `ep_recovery` use LLM levels when present; recovery is N/A without disruptions

##### Added - Category 8 visual aids and slides_v1 Glance Test (issue #44)
- All `va_*` scoring.yaml metrics, including reading-ratio 3-gram overlap
- `slides_v1` on at most 20 slides via the existing LLM client; missing key → glance N/A, never a fake level
- N/A when no slides and no deck; deck-only alignment multiplies reading-ratio confidence by 0.6
- Golden test on a synthetic screen-recording fixture

##### Added - Slides stage: PySceneDetect, keyframes, deck, OCR (issue #43)
- Slide region: full frame for screen recordings; stage uses a bright low-motion quadrilateral (H)
- Scene changes via PySceneDetect ContentDetector (BSD-3-Clause); merge gaps under 2 s; ffmpeg scene fallback
- Keyframe is the sharpest frame (Laplacian variance) in the first half of each segment
- python-pptx / pdftotext for uploaded decks; Tesseract `eng`/`por` otherwise (PaddleOCR not used)
- Video slides matched to deck pages with TF-IDF cosine or average-hash when OCR is sparse
- Sandbox antivirus: magic bytes, zip-bomb/macro/JS checks; ClamAV if `clamscan` is on PATH
- `POST /sessions/{id}/deck` stores PPTX/PDF beside the session; audio-only with no deck stays empty

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
