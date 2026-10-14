# Architecture Decision Records (ADRs)

This document tracks significant technical decisions made during Stage Coach development. Each ADR follows a lightweight format: Context, Decision, Alternatives Considered, Consequences.

---

## ADR-001: Monorepo Structure and Tech Stack

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 0

### Context

Stage Coach requires coordinated development across a web frontend, REST API, analysis workers, and shared libraries (scoring config, schemas, scoring engine). We need to choose an organization strategy that enables:
- Type safety across boundaries (API ↔ web)
- Shared configuration and schema versioning
- Independent deployment of services
- Developer velocity with hot reload

### Decision

Use a **monorepo** with the structure defined in §7.2 of the SPEC:
- **Frontend**: Next.js 14 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui
- **API**: Python 3.11+ FastAPI with pydantic v2, SQLAlchemy 2, Alembic
- **Workers**: Python Celery + Redis queue
- **Database**: PostgreSQL 16
- **Storage**: S3-compatible object storage (MinIO locally, R2/S3 in production)
- **Auth**: Auth.js (NextAuth) with email magic links + OAuth providers

### Alternatives Considered

1. **Polyrepo** (separate repos per service)  
   - ❌ Schema drift between API and web  
   - ❌ Harder to enforce shared scoring config versioning  
   - ❌ More complex CI/CD coordination

2. **NestJS API instead of FastAPI**  
   - ✅ Single language (TypeScript) across stack  
   - ❌ Analysis code (ASR, audio features, vision) is Python-native  
   - ❌ Scientific Python ecosystem (numpy, parselmouth, MediaPipe) has no good TS equivalent  
   - **Trade-off**: We accept Python API + TS frontend for access to the analysis ecosystem

3. **Temporal instead of Celery**  
   - ✅ Better visibility, retries, and long-running workflow support  
   - ❌ More infrastructure complexity in MVP  
   - 📅 Consider for v2 when multi-step rehearsal workflows arrive

### Consequences

- ✅ OpenAPI → generated TS client gives end-to-end type safety
- ✅ Scoring config and schemas live in shared `packages/`
- ✅ Single CI pipeline, single `make dev` command
- ⚠️ Developers need both Node and Python toolchains
- ⚠️ API and workers share Python dependencies but deploy separately

---

## ADR-002: Job Queue: Celery + Redis

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 0

### Context

Analysis pipelines have multiple stages (ingest, ASR, audio features, vision, LLM, scoring) with different resource needs (CPU, GPU, rate-limited LLM API). Stages must run in dependency order but can parallelize where independent. Failures should retry with backoff, and progress must stream to the browser.

### Decision

**Celery** with **Redis** as broker and result backend:
- Three queue priority levels: `cpu`, `gpu`, `llm`
- Celery **chords** and **groups** express the DAG  
- `acks_late=True`, idempotency keys `(session_id, stage, input_hash, stage_version)`  
- Exponential backoff (3 attempts)  
- Dead-letter queue on permanent failure → partial results  
- Progress events via Redis pub/sub → API streams via SSE

### Alternatives Considered

1. **Temporal**  
   - ✅ Native DAG support, excellent visibility, durable timers  
   - ❌ Heavyweight for MVP (separate Temporal server + workers)  
   - 📅 Strong candidate for v2+

2. **Dramatiq / Arq**  
   - ✅ Lighter than Celery, modern async Python  
   - ❌ Smaller ecosystem, less battle-tested for complex DAGs  
   - ❌ Team familiarity with Celery

3. **Cloud-native queues** (SQS, Pub/Sub, etc.)  
   - ❌ Lock-in  
   - ❌ Local dev requires emulators

### Consequences

- ✅ Well-known patterns, abundant documentation
- ✅ Local dev with docker-compose redis
- ⚠️ Celery's chord/group syntax can be verbose
- ⚠️ Progress streaming requires custom pub/sub layer on top of Celery
- 📌 Document idempotency contract in worker README

---

## ADR-003: S3-Compatible Storage + tus Resumable Uploads

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 0

### Context

Users upload video files up to 2 GB and 90 minutes. Uploads must be:
- Resumable (network drops, browser tab close)
- Direct to object storage (no API proxy of large binaries)
- Lifecycle-managed (automatic deletion per retention policy)

Derived artifacts (proxies, transcripts, keyframes) also need object storage with encryption at rest.

### Decision

- **Object storage**: S3-compatible API (AWS S3, Cloudflare R2, GCS via interop)  
- **Local dev**: MinIO in docker-compose  
- **Upload mechanism**: **tus** protocol via `tusd` server with S3 backend  
  - Client: `tus-js-client` or Uppy  
  - Presigned URLs for playback/download (15-minute expiry)  
  - Server-side encryption (SSE-KMS in production, SSE-S3 locally)

- **Retention**: S3 lifecycle rules + nightly `retention_sweeper` worker cross-checking DB `media_assets.retention_until`

### Alternatives Considered

1. **S3 multipart upload** with presigned POST/PUT per part  
   - ✅ No extra server (tusd)  
   - ❌ Client must implement chunking, retry, and part assembly  
   - ❌ More complex browser code

2. **Resumable upload via API proxy** (e.g., tus to API, API writes to S3)  
   - ❌ API becomes a bottleneck and bandwidth hog  
   - ❌ Doubles storage I/O

3. **Cloudflare Stream** or similar managed video service  
   - ✅ Transcoding and adaptive streaming included  
   - ❌ Cost and lock-in  
   - ❌ We need the original file for offline analysis anyway

### Consequences

- ✅ Tusd handles chunking, retry, and part coordination
- ✅ Direct S3 writes after chunk assembly
- ✅ Storage provider flexibility (swap S3/R2/GCS via env config)
- ⚠️ Tusd is another service to run and monitor
- 📌 Ensure tusd hook validates file types and size limits before accepting uploads

---

## ADR-004: Auth.js + API JWT Verification

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 0

### Context

MVP needs user authentication with:
- Email magic links (no password)  
- OAuth (Google, Microsoft)  
- Self-hostable (no vendor lock-in)  
- Secure API calls from the Next.js app

### Decision

**Auth.js** (NextAuth.js v5) in the Next.js app:
- Auth.js handles sign-in flows and issues JWTs (signed with `NEXTAUTH_SECRET`)  
- API receives `Authorization: Bearer <jwt>` headers  
- API verifies JWT signature using the shared JWKS endpoint or secret  
- Pydantic schema for decoded JWT claims (`user_id`, `email`, `org_id`)  
- Middleware extracts `user_id` and attaches to request context

Session flow:
1. User signs in via Auth.js → cookie + JWT  
2. Web app sends JWT in API calls  
3. API verifies + decodes → `request.user_id`  
4. All DB queries filter by `user_id` (authorization)

### Alternatives Considered

1. **Clerk / Auth0 / Supabase Auth**  
   - ✅ Managed, great DX  
   - ❌ Monthly cost per user or MAU  
   - ❌ Vendor lock-in for a core feature

2. **Roll our own** (password hashing, token management, email sending)  
   - ❌ Security risk (easy to get wrong)  
   - ❌ Time sink

3. **Lucia** (auth library)  
   - ✅ Lightweight, database-backed sessions  
   - ❌ Smaller ecosystem than Auth.js  
   - ❌ Less OAuth provider coverage

### Consequences

- ✅ No per-user SaaS fees
- ✅ Self-hostable, open-source
- ✅ Auth.js supports many OAuth providers out of the box
- ⚠️ JWT verification in Python requires careful implementation (check `exp`, `iss`, `aud`)
- ⚠️ Token refresh must be handled (short-lived access tokens + refresh tokens, or rely on Auth.js session refresh)
- 📌 Document JWT claims schema and verification flow in `services/api/app/auth/README.md`

---

## ADR-005: Versioned Scoring Config as Single Source of Truth

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 0

### Context

The scoring system has 17 categories, 60+ sub-metrics, and 6+ contexts, each with:
- Category weights per context (must sum to 100)  
- Sub-metric weights per category (must sum to 1.0)  
- Piecewise-linear scoring curves  
- Minimum evidence rules  
- Research source attributions

Scoring logic must be:
- Transparent (users can see the config that scored them)  
- Auditable (old reports can be regenerated)  
- Testable (config validates at build time)  
- Evolvable (weights and curves will be calibrated in Phase 4 per §11)

Hard requirements from §1.2 of SPEC:
- Never inline thresholds or weights in code  
- Every threshold must be traceable and labeled `research` or `heuristic`  
- Every analysis result records the config version used

### Decision

**Versioned YAML configuration files** in `packages/scoring-config/`:
```
packages/scoring-config/
  v1.0.0/
    scoring.yaml          # Complete config
    README.md             # Version changelog
  v1.1.0/                 # Future: calibrated curves
    scoring.yaml
    README.md
  scoring-config.schema.json  # JSON Schema validator
```

`scoring.yaml` structure:
- `version` (semver)  
- `weights` (map of context → category → weight)  
- `categories` (map of category id → sub-metrics, sources, min_evidence, tractability)  
- Each sub-metric: `weight`, `unit`, `basis: {kind, source}`, `curve` or `llm_level`

**Validation** (unit tests in `packages/scoring/tests/`):
- All context weights sum to 100  
- All category sub-metric weights sum to 1.0  
- Every `source` key exists in `docs/research/sources.md`  
- Curves are well-formed (sorted x, y in [0, 100])

**Usage**:
- Scoring engine loads config by version: `ScoringEngine(config_version="1.0.0")`  
- Analysis results embed `provenance.scoring_config_version`  
- API serves `/config/scoring/{version}` (read-only, public for transparency)

**Code never contains**:
- Inline weights or thresholds  
- Magic numbers for scoring

**Breaking changes** (major version bump):
- Category added/removed  
- Metric ID renamed  
- Weight structure change

**Non-breaking changes** (minor version bump):
- Weight value changes  
- Curve adjustments  
- New context added (with weights for all categories)

### Alternatives Considered

1. **Config in database**  
   - ✅ Runtime editable via admin UI  
   - ❌ Harder to version control and code review  
   - ❌ Versioning and rollback logic adds complexity  
   - ❌ Harder to validate at build time

2. **Config in code** (Python dicts or TS objects)  
   - ❌ Fails the "transparent and auditable" requirement  
   - ❌ Not human-reviewable by non-programmers  
   - ❌ Hard to diff versions

3. **TOML instead of YAML**  
   - ✅ Stricter spec, less ambiguity  
   - ❌ Less ecosystem support (YAML has better Python/TS libraries)  
   - ❌ Nested structures are more verbose

### Consequences

- ✅ Config is the source of truth; code reads it  
- ✅ Git history of config changes  
- ✅ Non-engineers (coaches, researchers) can review weight changes in PRs  
- ✅ Validation catches errors before deployment  
- ⚠️ Config parsing happens at runtime; bad YAML could crash workers (mitigated by validation in CI)  
- 📌 Immutability rule: once a version is used in production, it cannot be edited (create a new version instead)  
- 📌 Database `scoring_configs` table stores (version, yaml, sha256, created_at) for provenance

---

## ADR-006: (Placeholder for Phase 1)

Reserved for first major Phase 1 decision (likely ASR model and provider choice).

---

## Template for Future ADRs

```markdown
## ADR-NNN: Title

**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Superseded by ADR-XXX  
**Phase:** 0 | 1 | 2 | ...

### Context
What problem are we solving? What constraints exist?

### Decision
What we chose and key details.

### Alternatives Considered
1. **Option A**: Pros, cons, why not chosen  
2. **Option B**: Pros, cons, why not chosen

### Consequences
- ✅ Benefits  
- ⚠️ Trade-offs  
- ❌ Risks  
- 📌 Action items
```

---

## ADR-006: Type generation from JSON Schemas

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 0

### Context

The API and web frontend need to share TypeScript and Python types derived from our JSON Schema definitions (`analysis_result.v1.json`, future `talk_plan`, etc.). We need a strategy that:
- Generates pydantic v2 models for FastAPI request/response validation
- Generates TypeScript types for the Next.js frontend
- Stays in sync with schema changes
- Fails CI if generated code is stale

### Decision

1. **JSON Schemas** in `packages/schemas/` are the **single source of truth**
2. **Python pydantic v2 models** generated via `datamodel-code-generator` into `services/api/app/schemas/`
3. **TypeScript types** generated via `openapi-typescript` from FastAPI's OpenAPI spec (Phase 1+)
4. **CI check** (`scripts/check_generated.sh`) fails if `make generate-types` hasn't been run after schema changes
5. Generated files are **committed** to git (not gitignored) to enable quick builds without regeneration

### Alternatives Considered

1. **Manual types** (hand-write pydantic and TS)  
   - ❌ Schema drift inevitable  
   - ❌ No guarantee API matches frontend types

2. **Protocol Buffers / gRPC**  
   - ✅ Strong type generation  
   - ❌ Overkill for REST API  
   - ❌ Worse browser support than JSON

3. **Zod schemas shared via TS**  
   - ✅ Single TS schema definition  
   - ❌ Python can't consume Zod directly  
   - ❌ JSON Schema is more standard for documentation

### Consequences

- ✅ Type safety from JSON Schema → pydantic → OpenAPI → TypeScript  
- ✅ CI enforces sync via `make check-generated`  
- ⚠️ Developers must run `make generate-types` after schema changes  
- 📌 Add pre-commit hook to auto-generate (nice-to-have)

---

## ADR-007: LLM Provider and Client Architecture

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

Text analysis in Stage Coach requires an LLM for:
- Core message and structure extraction (categories 1, 2, 5, 6)
- Story and impact analysis (categories 3, 4, 7)
- Fluency disambiguation (category 11)
- Q&A quality (category 17)

Requirements:
- Structured outputs (strict JSON schema conformance) for reliable parsing
- Provider flexibility (no vendor lock-in)
- Per-token cost tracking and ceiling enforcement
- Deterministic testing without live API calls
- No raw video sent to the LLM (privacy constraint)

### Decision

**Provider:** xAI (Grok) API  
**Architecture:** Provider-neutral LLM client with pluggable adapters

**Implementation details:**
- `LLMClient.generate_structured(prompt_id, inputs, schema)` interface
- Provider, model, and per-token prices configured in `services/analysis/config/llm.yaml`, never hard-coded
- xAI adapter implements strict JSON-schema structured outputs
- Interface designed for easy addition of other providers (OpenAI, Anthropic, etc.)
- API key read from `LLM_API_KEY` environment variable
- VCR-style cassettes for deterministic CI tests
- Skip live LLM tests when `LLM_API_KEY` is absent
- Token usage and cost logged per call; analysis_jobs.cost tracks total
- Never send raw video frames or biometric data to the LLM

### Alternatives Considered

1. **OpenAI GPT-4**  
   - ✅ Excellent structured output support  
   - ✅ Well-documented, stable API  
   - ❌ Higher cost per token  
   - ❌ Not chosen by owner

2. **Anthropic Claude**  
   - ✅ Strong reasoning, good for analysis  
   - ✅ Structured outputs via tools  
   - ❌ Higher cost  
   - ❌ Not chosen by owner

3. **Open-source models (Llama, Mixtral)**  
   - ✅ No per-token cost  
   - ✅ Self-hostable  
   - ❌ GPU required for acceptable latency  
   - ❌ Contradicts CPU-only decision (D3)  
   - ❌ Structured output quality less reliable

### Consequences

- ✅ xAI Grok selected by owner, provides good structured output support
- ✅ Provider-neutral interface enables switching providers later
- ✅ Config-driven provider/model selection
- ✅ Cost tracking and ceiling enforcement built in
- ✅ Cassettes enable fast, deterministic CI without API keys
- ⚠️ Live API key required for production and integration testing
- 📌 Document LLM data flow in PRIVACY.md (no PII in prompts)
- 📌 Monitor cost per analysis; set alerts for anomalies

---

## ADR-008: CPU-Only Compute and ASR Model Selection

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

Production deployment target: Mac with OrbStack containers, which have no GPU access. Analysis pipeline must run on CPU and meet performance target: ≤1.5× media duration for 10-minute talks (≤15 minutes processing time).

Key compute-intensive stages:
- Automatic Speech Recognition (ASR)
- Audio feature extraction (F0, syllable nuclei)
- Video analysis (Phase 2: MediaPipe pose/hands/face)

### Decision

**Compute:** CPU only  
**ASR:** faster-whisper with small or medium model, int8 quantization  
**Target performance:** P50 ≤ 1.5× media duration

**ASR specifics:**
- faster-whisper (CTranslate2 backend) provides good CPU performance
- Models: small.en / small / medium (configurable, default small for dev)
- int8 quantization for faster inference
- BatchedInferencePipeline for efficiency
- Filler-preserving initial prompts (per-language)
- word_timestamps=True for precise alignment
- condition_on_previous_text=False to avoid hallucination drift

**Audio features:**
- Praat (parselmouth) for F0 extraction (two-pass with adaptive floor/ceiling)
- Syllable nuclei detection per de Jong & Wempe (Python port)
- All audio processing CPU-friendly

### Alternatives Considered

1. **CrisperWhisper** (filler-preserving Whisper variant)  
   - ✅ Better filler preservation  
   - ❌ CC-BY-NC-4.0 license (non-commercial restriction)  
   - ❌ Owner decision D5: keep it off

2. **WhisperX large-v3 model**  
   - ✅ Better accuracy  
   - ❌ Too slow on CPU (would exceed 1.5× target)

3. **GPU acceleration**  
   - ✅ 5-10× faster ASR  
   - ❌ Production environment (OrbStack on Mac) has no GPU  
   - ❌ Adds infrastructure complexity

4. **Cloud ASR APIs** (Google Speech-to-Text, AWS Transcribe, Deepgram)  
   - ✅ Fast, accurate, filler-preserving options available  
   - ❌ Per-minute cost  
   - ❌ Privacy: audio sent to third party  
   - ❌ Vendor lock-in

### Consequences

- ✅ Works in production environment (CPU-only containers)
- ✅ faster-whisper + int8 meets 1.5× performance target on modern CPUs
- ✅ No additional GPU infrastructure or cost
- ✅ Audio stays on-premise (privacy benefit)
- ⚠️ Filler preservation quality lower than CrisperWhisper (mitigated with filler prompts and LLM disambiguation)
- ⚠️ Performance degrades on older/slower CPUs (document minimum requirements)
- 📌 Benchmark on target Mac hardware before production
- 📌 Add performance regression tests: fail CI if 10-min fixture exceeds 20 min (1.5× + margin)

---

## ADR-009: Speaker Diarization Feature Flag

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

Category 17 (Q&A Handling) requires distinguishing the primary speaker from questioners. Speaker diarization solves this, but:

1. **Model availability:** Best open-source option is pyannote.audio's `speaker-diarization-community-1` pipeline
2. **License gate:** The model is gated on Hugging Face and requires accepting terms
3. **CI constraint:** Cannot download gated models in CI without credentials
4. **Fallback needed:** System must work without diarization for development and when the token is unavailable

### Decision

**Diarization:** pyannote `speaker-diarization-community-1` behind a feature flag  
**Feature flag:** Enabled only when `HF_TOKEN` environment variable is present  
**Fallback:** When disabled, use LLM-based heuristic from spec (detect "repeat the question" phrases, low confidence)

**Implementation:**
- Diarization stage checks for `HF_TOKEN` at runtime
- If absent: skip diarization, set `diarization_available=false` in pipeline metadata
- If present: authenticate with Hugging Face, download/cache model, run diarization
- Category 17 (Q&A) scoring:
  - With diarization: full confidence, speaker-change boundaries
  - Without diarization: fallback to LLM-based Q&A detection, confidence capped at 0.6 (H)
- CI: no `HF_TOKEN` → diarization tests skipped, fallback path tested
- Production: `HF_TOKEN` provided → full diarization enabled

**Gated model compliance:**
- Document that `HF_TOKEN` requires accepting pyannote model terms
- Never download gated models in CI or without explicit token
- README and PRIVACY.md note this optional dependency

### Alternatives Considered

1. **Require diarization always**  
   - ❌ Breaks CI without HF token  
   - ❌ Blocks development for contributors without token

2. **Use a non-gated diarization model**  
   - ❌ pyannote is state-of-the-art; alternatives (e.g., resemblyzer + spectral clustering) have worse accuracy  
   - ❌ Building custom diarization is out of scope for MVP

3. **Cloud diarization APIs** (AWS Transcribe, Google, Deepgram)  
   - ❌ Per-minute cost  
   - ❌ Privacy: audio sent to third party  
   - ❌ Vendor lock-in

4. **LLM-only Q&A detection (no diarization)**  
   - ✅ Works without extra models  
   - ❌ Lower accuracy, especially for short or overlapping questions  
   - ✅ Used as fallback

### Consequences

- ✅ Best-in-class diarization when `HF_TOKEN` is available
- ✅ System works (with degraded Q&A scoring) when token is absent
- ✅ CI passes without gated model download
- ✅ Contributors can develop without HF account
- ⚠️ Two code paths to test (with/without diarization)
- ⚠️ Production deployment must provide `HF_TOKEN` for full Q&A analysis
- 📌 Document in README: "Optional: Set HF_TOKEN for speaker diarization (improves Q&A analysis)"
- 📌 Add note in category 17 report card when diarization was unavailable

---

## ADR-010: Excluded Models and Licenses

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

Owner decisions specify models and libraries to exclude due to license restrictions, ethical concerns, or scope constraints.

### Decision

**Excluded:**
- **CrisperWhisper:** CC-BY-NC-4.0 license (non-commercial) – keep off (D5)
- **openSMILE:** License restrictions for commercial use – not used (D5)
- **OpenFace:** Emotion inference models – not used (D5)
- **Speech Emotion Recognition (SER) models:** Emotion inference out of scope (D5)
- **Any emotion inference models:** See §5 and §10.4 of SPEC – ethical constraint

**Allowed (verified licenses):**
- **librosa:** ISC License (permissive) – used for audio I/O and basic features
- **parselmouth:** GPL-3.0 (OK for server-side use; ADR records this) – used for F0 extraction
- **MediaPipe:** Apache-2.0 – used for pose/hands/face landmarks (Phase 2)

**Emotion analysis constraint:**
- No models that claim to infer emotions from expressions or voice
- Facial expression analysis (category 14) is opt-in and **descriptive only**: "smile detected", "brow raised", never "happy" or "anxious"
- Report text must use "expression signals" or "affect signals", never "emotion"

### Alternatives Considered

1. **Use openSMILE for voice quality features**  
   - ❌ License unclear for commercial use

2. **Use CrisperWhisper for better filler preservation**  
   - ❌ Non-commercial license

3. **Infer emotions from expressions**  
   - ❌ Ethical risk: expressions ≠ emotions (see §5)  
   - ❌ Violates §10.4 fairness principles  
   - ❌ Owner explicitly ruled out

### Consequences

- ✅ All dependencies are commercially licensed or open-source permissive
- ✅ parselmouth (GPL-3.0) is server-side only (no distribution to end users) – acceptable use
- ✅ No pseudo-scientific emotion inference
- ✅ Responsible affect analysis: describe observations, never infer internal states
- ⚠️ Filler preservation slightly worse without CrisperWhisper (mitigated with prompts + LLM disambiguation)
- 📌 Maintain LICENSES.txt with all dependencies and their licenses
- 📌 Add CI check: fail if forbidden terms ("happy", "sad", "angry", "anxious", "fearful") appear in category 14 code or report text (en and pt-BR)

---

## Change Log

---

## ADR-011: Ingest Stage Implementation

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

The ingest stage is the pipeline's entry point and must:
- Validate media files safely (no arbitrary code execution)
- Enforce size and duration limits
- Produce optimized transcodes for downstream stages
- Detect modality for stage applicability (N/A rules)

Per SPEC §6.2 and issue #17.

### Decision

**Validation**: ffprobe with subprocess parameterization (no shell strings)  
**Transcoding**: ffmpeg with three outputs:
- ASR audio: 16kHz mono WAV with loudness normalization (EBU R128 I=-16:TP=-1.5:LRA=11)
- Analysis video: ≤720p, 15fps H.264, no audio (efficient for CV processing)
- Playback video: H.264+AAC, faststart flag (web-optimized streaming)

**Sprite thumbnails**: Every 5 seconds at 160px width for timeline hover previews

**Modality detection**:
- Audio-only: Check for video stream presence
- Screen recording vs person video: Frame variance heuristic (improved with MediaPipe in Phase 2)
- Person detection confidence score (0-1)

**Limits** (heuristic, from SPEC §6.2):
- Max file size: 2 GB
- Max duration: 90 minutes

**Safety**:
- Parameterized subprocess calls (no shell=True, no string interpolation)
- Timeout on all ffmpeg/ffprobe operations
- Temp directory isolation for artifacts

**Supported formats**:
- Video containers: mov, mp4, webm, mkv, avi
- Audio containers: mp3, m4a, wav, ogg, flac
- Video codecs: h264, hevc, vp8, vp9, av1
- Audio codecs: aac, mp3, opus, vorbis, flac, pcm_s16le

### Alternatives Considered

1. **MediaInfo library instead of ffprobe**
   - ❌ Less detailed codec information than ffprobe
   - ❌ ffmpeg is already required for transcoding

2. **Cloud transcoding service** (AWS MediaConvert, Cloudflare Stream)
   - ❌ Per-minute cost
   - ❌ Privacy: media uploaded to third party
   - ❌ Vendor lock-in

3. **Single transcode for both analysis and playback**
   - ❌ 15fps is too choppy for user-facing playback
   - ❌ Analysis video doesn't need audio track (wastes storage)

4. **MediaPipe for person detection in ingest**
   - ✅ More accurate than frame variance
   - ❌ Adds significant processing time to ingest (deferred to Phase 2 vision stage)
   - ✅ Frame variance is good enough for modality flagging

### Consequences

- ✅ Parameterized subprocess calls prevent shell injection attacks
- ✅ Three transcodes optimize for different consumers (ASR, CV, web playback)
- ✅ Loudness normalization only on ASR copy preserves dynamics for prosody analysis
- ✅ Clear validation errors with limits guide users to supported formats
- ✅ SHA256 hash provides content verification and idempotency key component
- ⚠️ ffmpeg transcoding is CPU-intensive (mitigated: runs async in Celery worker queue)
- ⚠️ Person detection heuristic has false positives (acceptable; improved in Phase 2)
- 📌 Benchmark transcoding time on target hardware (target: ≤ 0.3× media duration for ingest)
- 📌 Monitor storage usage of three transcodes (mitigated by retention policies §10.3)

---

## Change Log

- **2026-10-09**: ADR-001 through ADR-006 (Phase 0 foundations)
- **2026-10-09**: ADR-007 through ADR-010 (Phase 1: owner decisions D2, D3, D4, D5/D6)
- **2026-10-09**: ADR-011 (Phase 1: ingest stage implementation)
- **2026-10-09**: ADR-012 (Phase 1: DAG orchestration and SSE progress #18, #19)
- **2026-10-10**: ADR-013 (Phase 1: parselmouth GPL server-only for audio features #24)
- **2026-10-09**: ADR-014 (Phase 1: WhisperX alignment with VAD and gap detection #21)
- **2026-10-09**: ADR-015 (Phase 1: Speaker diarization with pyannote gated model #22)
- **2026-10-14**: ADR-016 (Phase 1: pure metric functions with scoring.yaml units #25)

---

## ADR-015: Speaker Diarization with Pyannote (HF_TOKEN Feature Gate)

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

Category 17 (Q&A Handling) requires distinguishing the primary speaker from questioners. Speaker diarization solves this, but:
- Best open-source model is pyannote/speaker-diarization-community-1 (gated on Hugging Face)
- CI cannot download gated models without credentials
- System must work without diarization for development

### Decision

**Diarization:** pyannote/speaker-diarization-community-1 behind HF_TOKEN feature flag  
**License:** CC-BY-4.0 (permissive, requires attribution)  
**Feature gate:** `HF_TOKEN` environment variable  
**Fallback:** When disabled, use LLM-based Q&A detection per SPEC §6.3

**Implementation:**
- `diarization.py` checks `HF_TOKEN` at module load
- If absent: skip diarization, return fallback output with `fallback_mode=True`
- If present: authenticate with HF, run pyannote pipeline
- Primary speaker = speaker with most total speech time
- Category 17 scoring:
  - With diarization: full confidence, speaker-change boundaries
  - Without: LLM spots "repeat the question", confidence capped at 0.6 (H)

**CI behavior:**
- No `HF_TOKEN` → diarization tests skipped via `@pytest.mark.skipif`
- Fallback test runs always (ensures graceful degradation)
- Never download gated models in CI

**Production:**
- Set `HF_TOKEN` via Cursor Dashboard (Cloud Agents > Secrets) or env config
- Token requires accepting pyannote/speaker-diarization-community-1 terms on Hugging Face

**Attribution:**
- CC-BY-4.0 requires attribution
- Credit pyannote in `/about` page and model registry
- Attribution text: "Speaker diarization powered by pyannote.audio (CC-BY-4.0)"

### Alternatives Considered

1. **Require diarization always**  
   - ❌ Breaks CI without HF token  
   - ❌ Blocks development for contributors without token

2. **Non-gated diarization model**  
   - ❌ pyannote is state-of-the-art  
   - ❌ Alternatives (resemblyzer + clustering) have worse accuracy

3. **Cloud diarization APIs** (AWS Transcribe, Deepgram)  
   - ❌ Per-minute cost  
   - ❌ Privacy: audio sent to third party  
   - ❌ Vendor lock-in

4. **LLM-only Q&A detection (no diarization)**  
   - ✅ Works without extra models  
   - ❌ Lower accuracy for short or overlapping questions  
   - ✅ Used as fallback

### Consequences

- ✅ Best-in-class diarization when `HF_TOKEN` is available
- ✅ System works (with degraded Q&A scoring) when token is absent
- ✅ CI passes without gated model download
- ✅ Contributors can develop without HF account
- ✅ CC-BY-4.0 attribution properly credited
- ⚠️ Two code paths to test (with/without diarization)
- ⚠️ Production deployment must provide `HF_TOKEN` for full Q&A analysis
- 📌 Document in README: "Optional: Set HF_TOKEN for speaker diarization (improves Q&A analysis)"
- 📌 Add note in category 17 report card when diarization was unavailable
- 📌 List owner decision needed: D4 HF token (not yet supplied)

---

## ADR-012: Celery DAG Orchestration with Job Steps Tracking

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

Issues #18 and #19 require a robust pipeline orchestration system with:
- Individual stage tracking and re-runnability
- Progress streaming to the browser during analysis
- Idempotency for safe retries
- Graceful handling of partial failures

The existing worker had standalone tasks for ingest and ASR but no coordination layer.

### Decision

**Orchestration:** PipelineOrchestrator class manages DAG execution via Celery chains
**Job tracking:** job_steps table records (job_id, stage, status, input_hash, stage_version, output_uris, metrics, timing, error)
**Status values:** 
- JobStep: pending → running → succeeded | failed | skipped
- AnalysisJob: pending → running → succeeded | failed | partial
- Session: created → uploaded → processing → ready | partial | failed

**Idempotency:** Hash of (session_id, stage, inputs, stage_version) prevents duplicate processing
**Progress streaming:** Tasks emit events to Redis pub/sub channel `progress:{job_id}` with {stage, status, pct, eta_s, message, timestamp}
**SSE endpoint:** `GET /sessions/{id}/events` streams progress via Server-Sent Events with reconnect support

**Task chaining:** Ingest result passes `audio_path` to ASR via Celery chain signature:
```python
chain(
    ingest_task.s(input_path, output_dir, session_id, job_id),
    asr_task.s(output_dir, session_id, language, model_name, job_id)
)
```

**Retries:** Celery task decorators handle exponential backoff (4s, 16s, 64s) for 3 attempts
**Partial status:** Non-critical stage failures (e.g., diarization when HF_TOKEN absent) mark job as "partial" and continue

### Alternatives Considered

1. **Task polling instead of Redis pub/sub**  
   - ❌ Higher latency, more API load  
   - ❌ No live streaming

2. **WebSocket instead of SSE**  
   - ✅ Bidirectional (not needed here)  
   - ❌ More complex client code  
   - ❌ Harder to deploy through proxies

3. **Store all progress in DB**  
   - ❌ High write load for fine-grained updates  
   - ✅ SSE reads from ephemeral Redis pub/sub, final state in DB

4. **Temporal Workflow instead of Celery**  
   - ✅ Better observability and retry logic  
   - ❌ More infrastructure complexity for MVP  
   - 📅 Consider for v2

### Consequences

- ✅ Each stage is independently re-runnable via POST /sessions/{id}/reanalyze?from_stage=X
- ✅ Browser shows live progress with ETA during 10+ minute analysis
- ✅ Idempotency prevents wasted computation on retries
- ✅ Job history visible in job_steps for debugging
- ⚠️ Redis pub/sub is ephemeral: if client disconnects and misses events, it must reconnect (SSE handles this)
- ⚠️ Progress percentages and ETAs are estimates; tasks emit them when possible
- 📌 Document progress event schema in API README
- 📌 Add smoke test: start job, verify SSE receives "succeeded" events

---

## ADR-013: Parselmouth / Praat is server-side only (GPL)

**Date:** 2026-10-10  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #24 and SPEC §6.4 require research-grade F0, intensity, and syllable-nucleus extraction. The specified library is **parselmouth** (Praat in Python) [S45], licensed **GPL-3.0-or-later**. SPEC §6.9 allows this only as server-side use with no distribution to clients, and requires an ADR.

openSMILE / eGeMAPS [S44] would give standardized GeMAPS features but needs a commercial license for product use. It stays out of the worker.

### Decision

- Use **praat-parselmouth** only inside `services/analysis` (Celery worker). Do not import it from `apps/web`, ship it in a browser bundle, or vendor Praat into a client app.
- Compute F0 with Praat autocorrelation, two-pass speaker-adaptive floor/ceiling `[q15·0.83, q65·1.92]` (H), then remove octave jumps > 10 st.
- Port de Jong & Wempe (2009) [S25] syllable nuclei on the Praat intensity + voiced mask.
- Use **librosa** (ISC) for spectral-flatness music/noise heuristics only. Do not add openSMILE to the product path.
- Record `basis` + source keys (`S24`, `S25`, `S45`) on every `audio_metrics.json`.
- Energy-based VAD is the standalone pause detector in this stage. Silero VAD arrives with WhisperX alignment (#21) and can replace the energy VAD later without changing the artifact schema.

### Alternatives Considered

1. **openSMILE / eGeMAPS in the worker**  
   - ✅ Standardized feature set  
   - ❌ Commercial license required for products [S44]

2. **Pure librosa / numpy F0 (piptrack, yin)**  
   - ✅ Permissive licenses  
   - ❌ Weaker voiced/unvoiced decisions than Praat AC for presentation speech  
   - ❌ SPEC names parselmouth as the F0 source

3. **Bundle Praat in the Next.js app for live overlay**  
   - ❌ GPL distribution to end users  
   - ❌ Live overlay is a v2 client-side MediaPipe + Web Audio path (§3.2)

### Consequences

- ✅ Matches SPEC §6.4 and §6.9
- ✅ No GPL code is shipped to browsers
- ⚠️ Anyone distributing the worker image or a desktop build that includes parselmouth must treat that binary as a GPL work
- ⚠️ Energy VAD is a heuristic until Silero is wired from #21
- 📌 Keep parselmouth out of `apps/web` and any client package; a CI grep can enforce this later

---

## ADR-014: WhisperX Forced Alignment with VAD and Gap Detection

**Date:** 2026-10-09  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #21 requires precise word boundaries and recovery of fillers that Whisper drops. Whisper's word_timestamps are approximate; accurate alignment is needed for:
- Fluency metrics (filler detection depends on precise timing)
- Pace and pausing analysis (requires exact word boundaries)
- Gap detection (identifying > 300ms speech gaps where fillers may have been dropped)

### Decision

**Alignment:** WhisperX forced alignment with wav2vec2 models  
**VAD:** Silero VAD for speech/non-speech segmentation  
**Gap detection:** Identify speech gaps > 300ms between aligned words  
**Gap filling:** Acoustic fallback labels gaps as `[filler_candidate]` with low confidence

**Models (all licenses verified permissive):**
- en: `facebook/wav2vec2-large-960h-lv60-self` (Apache-2.0)
- pt: `jonatasgrosman/wav2vec2-large-xlsr-53-portuguese` (Apache-2.0)
- VAD: Silero VAD (MIT)
- WhisperX: BSD-2-Clause

**Pipeline flow:**
```
audio16k.wav + transcript.json
  ↓
1. Load Silero VAD → speech/non-speech segments
2. WhisperX align (wav2vec2) → precise word boundaries
3. Detect gaps: aligned_words[i].end to [i+1].start > 300ms AND overlaps VAD speech
4. Fill gaps: acoustic fallback `[filler_candidate]` (score=0.3, source=acoustic_fallback)
```

**Word source tracking:**
- `whisper_asr`: Original aligned words from WhisperX
- `gap_detector`: Re-decoded gaps (future: use Whisper beam search on gap audio)
- `acoustic_fallback`: Placeholder for gaps that can't be decoded

**Output:** `{session_id}_alignment.json` with `{aligned_words, vad_segments, gap_fills_count, acoustic_fallback_count, mean_alignment_score}`

### Alternatives Considered

1. **Gentle forced aligner**  
   - ❌ Less accurate than WhisperX  
   - ❌ Older Kaldi-based models

2. **Montreal Forced Aligner**  
   - ✅ Very accurate  
   - ❌ Requires grapheme-to-phoneme models per language  
   - ❌ More setup complexity than WhisperX

3. **Skip alignment, use Whisper word timestamps directly**  
   - ❌ Too imprecise for fluency and pacing metrics  
   - ❌ No gap detection possible

4. **Re-decode gaps with beam search** (future)  
   - ✅ Better filler recovery than acoustic fallback  
   - ⚠️ Phase 1: acoustic fallback is sufficient; beam search in Phase 2

5. **WebRTC VAD instead of Silero**  
   - ❌ Less accurate  
   - ✅ Silero is state-of-the-art and MIT licensed

### Consequences

- ✅ Precise word boundaries enable accurate fluency and pacing metrics
- ✅ Gap detection recovers some dropped fillers (acoustic fallback)
- ✅ VAD segments can be used for silence/pause analysis
- ✅ All dependencies are permissively licensed (Apache-2.0, MIT, BSD-2)
- ⚠️ WhisperX alignment adds ~30s overhead for 10-min talks on CPU
- ⚠️ Acoustic fallback has low confidence (0.3); LLM disambiguation needed downstream
- 📌 Phase 2: implement gap-detector re-decoding with Whisper beam search
- 📌 Benchmark alignment time on target hardware (target: ≤0.5× media duration)

## ADR-016: Pure metric functions, units from scoring.yaml

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #25 requires pace, vocal-variety, fluency, and time-management sub-metrics as **pure functions** (SPEC §1.4): dataclasses out, no hidden global state, each docstring listing definition, units, source or heuristic, and failure modes. Metric names and units must match `packages/scoring-config/v1.0.0/scoring.yaml` exactly so the scoring engine can consume them later.

### Decision

- Put functions in `services/analysis/metrics/{pace,prosody,fluency,timing}.py`.
- Persist a `metrics.json` artifact after `audio_features` (cpu queue) so the smoke fixture writes both audio features and metrics.
- Confidence follows SPEC §4.6.2: ASR = mean word probability × coverage; prosody = voiced-frame ratio × SNR factor (10 dB → 0.3, 20 dB → 1.0) × (1 − octave-error ratio).
- Combined filler rate is shown next to the 5/min and 12/min [S12] anchors. Grammar remains an optional LLM level (N/A until a later stage).
- No new third-party libraries. No openSMILE, SER, or emotion models.

### Alternatives Considered

1. **Inline formulas in `mvp_report.py`**  
   - ❌ Hidden thresholds; hard to unit-test; drifts from scoring.yaml units

2. **Put functions in `packages/scoring`**  
   - ❌ Scoring engine maps raw values to scores; extraction belongs with the worker (Appendix D)

### Consequences

- ✅ Synthetic tests can assert known WPM, PVQ, filler rates, and SNR confidence without audio libraries
- ✅ Units stay in lockstep with scoring.yaml via a dedicated unit-match test
- ⚠️ `fl_grammar_llm` stays N/A until the content-LLM stage supplies a level

---

## ADR-017: Fusion scores only existing artifacts; missing categories are N/A

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #30 requires `fusion_scoring` and `report` for categories 1–7, 9–11, and 15 (audio/text). Video categories and any metric without an existing input must not be invented. `scoring.yaml` v1.0.0 is the only source of curves, weights, and names.

### Decision

- Fusion reads `metrics.json`, `audio_metrics.json`, `transcript.json`, and `content.json` when present. It never synthesizes a raw value that those files do not contain.
- Categories 8, 12–14 are always N/A in this phase, with an explicit reason.
- Categories 1–7 are N/A unless `content.json` exists and min-evidence rules pass.
- Coach text is a facts-only template (`coach_text` in the report stage). Every number in prose is checked against the facts payload. No emotion terms.
- Drill IDs come from `packages/scoring-config/v1.0.0/drill_rules.yaml` (SPEC §7.8 excerpt).
- Result tables (`transcripts`, `metric_values`, `category_scores`, `overall_scores`, `evidence_items`, `insights`) persist scores when `job_id` is a UUID.
- Context-specific curves that omit the current context reuse an existing published curve (keynote, else the first listed). That is not a new curve.

### Alternatives Considered

1. **Call content_llm inside fusion when content.json is missing**  
   - ❌ Invents a live LLM dependency for scoring; smoke has no API key

2. **Keep `mvp_report.py` as the production report**  
   - ❌ Inline curves; does not validate `analysis_result.v1.json`

### Consequences

- ✅ Honest partial reports on the 3-second CI fixture
- ✅ Schema-valid `analysis_result.json` / `report.json` with provenance
- ⚠️ Category 15 is often N/A until intensity-trajectory fields exist in `audio_metrics.json`
- 📌 Do not add emotion labels to coach text (enforced in tests)

---

## ADR-018: Report API is owner-scoped with signed playback and token-bucket limits

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #31 adds the report read API from SPEC §7.5. MinIO is not in the CI smoke profile, so playback cannot depend on an S3 presign. Every resource must be owner-checked.

### Decision

- All report endpoints load the latest job for a session the JWT user owns. Other users receive 404.
- `GET /media/playback` returns an HMAC-signed URL (AUTH_SECRET) with a 15-minute expiry. The player fetches `GET /media?exp=&sig=` without a JWT.
- Series `pace`/`pitch`/`loudness`/`energy` are 1-s JSON written by fusion. Video series (`gesture`, `gaze`, `expressivity`) return an explicit unavailable series rather than invented values.
- Disputes persist `user_disputed` and `dispute_note` on `evidence_items`.
- Rate limits are Redis token buckets (per bearer token prefix and per IP) on `/api/v1`.

### Alternatives Considered

1. **S3 presign only**  
   - ❌ CI smoke skips MinIO

2. **Return FileResponse from /media/playback**  
   - ❌ Spec asks for a short-lived URL the player can load

### Consequences

- ✅ GET /report in smoke returns the same `report.json` the worker wrote
- ⚠️ Playback URLs are valid for anyone who has the link until expiry — treat like a presigned object URL

---

## ADR-019: Report v1 UI plots only available pillars

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #32 is the first report page. The analysis_result from #31 already marks missing pillars and categories with `score: null` and `applicable: false`. The UI must not turn those into zeros on the radar, and it must stay keyboard-accessible without a charting library.

### Decision

- Consume `GET /sessions/{id}/report` as the analysis_result view model from #31. Do not keep the private-beta metric-card layout.
- Radar is a 6-axis SVG. Unavailable pillars (`score === null`) are omitted from the polygon (a gap) and labelled unavailable in the table. They are never drawn at 0.
- Category cards that are not applicable are grey, show `na_reason`, and never display a numeric score.
- Key-metric info controls are buttons that open a dialog with definition, source or heuristic, and confidence.
- Copy lives in next-intl `en` and `pt-BR`. A unit test rejects emotion-inference words in those files.

### Alternatives Considered

1. **Chart.js / Recharts radar**  
   - ❌ Extra dependency for one chart; harder to leave honest gaps for N/A axes

2. **Keep the private-beta report layout**  
   - ❌ Does not match §8.1–8.3 (overall ± band, pillars, category cards)

### Consequences

- ✅ Partial audio/text reports can render before vision exists
- ⚠️ Player seeking, transcript highlights, and Voice tab graphs stay for issue #33
- 📌 Do not plot a null pillar at the origin

---

## ADR-020: Client-side transcript highlights and voice graphs

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #33 needs clickable evidence, transcript highlights, and voice graphs. The report API already returns `/transcript`, `/series/{name}`, and signed `/media/playback`. Series from fusion are often sparse on the 3 s smoke fixture.

### Decision

- Seek target is `max(0, t_start − 2)`. Tests assert the error is ≤ 0.5 s.
- The player is a focused region with Space / arrows / J / L. Captions come from a VTT blob of the existing transcript.
- Highlights label existing words using Appendix A lists and ASR tags. CLT and core-message spans come only from API highlights/evidence, never invented.
- Pace windows and pause histograms are computed from transcript timestamps. Pitch/loudness use `/series` points with numeric values; `unavailable: true` series are omitted, not drawn at 0.
- Filler-per-section bars include the 5/min and 12/min [S12] reference lines.
- The BFF forwards only `exp` and `sig` query params so signed playback URLs work through `/api/stagecoach`.

### Alternatives Considered

1. **A charting library for Voice tab**  
   - ❌ Extra dependency; SVG matches the radar from #32

2. **Treat missing series points as 0**  
   - ❌ Violates the N/A rule from #32 / §4.6.1

### Consequences

- ✅ Partial fixtures still render Transcript and Voice tabs honestly
- ⚠️ Pitch and loudness graphs are often unavailable until fusion writes F0/intensity series
- 📌 Do not invent CLT highlights without impact evidence

---

## ADR-022: Golden fixtures are synthetic; 20 min validation uses annotated timestamps

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 1

### Context

Issue #35 asks for three consented/licensed short audio fixtures (en + pt-BR), `scripts/process_local.py --golden` with ±2 score / ±5% metric tolerances, a noisy fixture that is Low confidence and excluded from overall, and validation of fillers/WPM/pauses started on ≥ 20 min annotated audio per language. The repo is public. `*.wav` is gitignored. Owner decision D13 (fixture sourcing) has not licensed personal recordings.

### Decision

- Three fixtures (`en_clean`, `ptbr_clean`, `noisy_low_snr`) are 16 kHz mono sines written with the stdlib `wave` module (CC0 generated signals). WAVs are produced at test time, not committed.
- Golden comparison runs fusion on committed `metrics.json` / `transcript.json` / `audio_metrics.json` against `expected/analysis_result.json`. Transcripts span 180 s so min_evidence can pass without storing long media.
- Noisy fixture: SNR 10 dB, metric confidence 0.3 (`include_none_below` / `category_min_for_overall`). Overall score is null, not zero.
- ≥ 20 min per language is a synthetic annotated timestamp corpus in `validation_corpus.py`. Results go in `docs/VALIDATION.md`. That starts §11.1; it is not a human-rated dataset.

### Alternatives Considered

1. **Commit personal or scraped talks**  
   - ❌ Public repo; issue forbids personal recordings without an explicit license

2. **Commit 20 min of WAV per language**  
   - ❌ gitignored media policy; large binaries; still not consented speech

3. **Skip noisy overall-exclusion until real noise recordings exist**  
   - ❌ Phase 1 AC requires the Low-confidence path

### Consequences

- ✅ CI can run `--golden` without ffmpeg TTS or Whisper
- ⚠️ Metric validation on synthetic timestamps will need a licensed corpus before §11.2 claims
- 📌 Do not add real recordings unless the owner licenses them (D13)

