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

## Change Log

- **2026-10-09**: ADR-001 through ADR-005 (Phase 0 foundations)
