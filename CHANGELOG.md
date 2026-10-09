# Changelog

All notable changes to Stage Coach will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
