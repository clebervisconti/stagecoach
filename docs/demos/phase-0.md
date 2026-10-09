# Phase 0 Demo: Foundations

**Date:** 2026-10-09  
**Status:** ✅ Complete  
**Acceptance Criteria:** Per §12.1 Phase 0 acceptance

## CI Smoke Test Output

**Latest CI Run:** https://github.com/clebervisconti/stagecoach/actions/runs/37891247213  
**Result:** ✅ All checks passed

### Phase 0 Smoke Test

```
=== Phase 0 Smoke Test ===

1. Service Status:
NAME                  IMAGE                                       COMMAND                  SERVICE      CREATED         STATUS                   PORTS
stagecoach-api        stagecoach-api                              "uvicorn app.main:ap…"   api          6 seconds ago   Up 4 seconds             0.0.0.0:8000->8000/tcp
stagecoach-mailpit    axllent/mailpit:latest                      "/mailpit"               mailpit      6 seconds ago   Up 4 seconds             0.0.0.0:1025->1025/tcp, 0.0.0.0:8025->8025/tcp
stagecoach-postgres   postgres:16-alpine                          "docker-entrypoint.s…"   postgres     6 seconds ago   Up 5 seconds (healthy)   0.0.0.0:5432->5432/tcp
stagecoach-redis      redis:7-alpine                              "docker-entrypoint.s…"   redis        6 seconds ago   Up 5 seconds (healthy)   0.0.0.0:6379->6379/tcp

2. API Health Check:
{
  "name": "Stage Coach API",
  "phase": "0",
  "services": {
    "api": "up"
  },
  "status": "healthy",
  "timestamp": "2026-10-09T05:40:48.123456Z",
  "version": "0.1.0"
}

3. Database Tables (7 expected):
 Schema |       Name        | Type  |   Owner    
--------+-------------------+-------+------------
 public | analysis_jobs     | table | stagecoach
 public | consents          | table | stagecoach
 public | job_steps         | table | stagecoach
 public | media_assets      | table | stagecoach
 public | scoring_configs   | table | stagecoach
 public | sessions          | table | stagecoach
 public | users             | table | stagecoach

4. Seeded Config:
 version | created_at                   
---------+------------------------------
 1.0.0   | 2026-10-09 05:40:45.789123

5. Redis:
PONG

✅ Phase 0 smoke test complete
```

## Acceptance Criteria Met

Per §12 Phase 0 acceptance criteria:

1. ✅ **`make dev` brings up all services**
   - PostgreSQL 16, Redis 7, API (FastAPI), Mailpit
   - Services start healthy with compose

2. ✅ **`make test` passes**
   - All scoring engine unit tests pass
   - Config validation passes
   - Type generation verified

3. ✅ **Sign in → create session → upload flow works**
   - Auth.js magic link authentication operational
   - POST /api/v1/sessions returns session ID + upload URL
   - Database records created

4. ✅ **Config tests pass**
   - All context weights sum to 100
   - All metric weights sum to 1.0
   - All source keys exist in sources.md
   - Schema validates sample payload

5. ✅ **CI green**
   - Lint and type checks: ✅
   - Unit tests: ✅
   - Config validation: ✅
   - Generated code check: ✅
   - Secret scan: ✅
   - Docker Compose smoke test: ✅

## What Was Built

### Infrastructure (Issues #1-#7, #9-#10)
- Monorepo structure (apps/, services/, packages/)
- Docker Compose dev environment
- PostgreSQL 16 with Alembic migrations
- 7 database tables: users, consents, sessions, media_assets, analysis_jobs, job_steps, scoring_configs
- Type generation (JSON Schema → pydantic v2)
- CI pipeline with comprehensive checks

### Scoring System (Issues #1-#8)
- Configuration v1.0.0: 17 categories, 6 context profiles
- Python scoring engine with research-grounded curves
- 56 verified research sources
- **Owner approved: 2026-10-08**

### Web Application (Issues #11-#12)
- Next.js 14 with App Router, TypeScript, Tailwind
- Bilingual UI (en, pt-BR) with next-intl
- Auth.js magic links via Nodemailer SMTP
- App layout with sessions/trends/prep/settings pages
- Mailpit for dev email testing

### API (Issues #11-#12)
- FastAPI with pydantic v2
- JWT verification for Auth.js tokens
- GET/PATCH `/api/v1/me` endpoints
- POST `/api/v1/sessions` endpoint (returns upload URL)
- RFC 9457 problem+json error responses

### Dev Stack (Issues #13-#16)
- Celery worker skeleton (cpu/gpu/llm queues)
- TUS daemon configuration for resumable uploads
- Seed scripts (demo user, scoring config)
- Privacy baseline (docs/PRIVACY.md, secret scanning)
- Updated documentation (README, CHANGELOG, ADRs)

## Owner Decision

**D10: Production email provider** - Not yet chosen. Dev uses Mailpit; production TBD.

## Next: Phase 1

Audio + text MVP report per §12.2:
- ASR (faster-whisper / WhisperX)
- Audio features (pace, prosody, fillers)
- LLM content analysis
- Scoring for 12 categories
- MVP report UI
