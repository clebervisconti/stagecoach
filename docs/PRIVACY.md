# Privacy and Security - Stage Coach

**Status**: Phase 0 stub. Full documentation in Phase 3.

## Overview

Stage Coach handles sensitive data including:
- User recordings (video/audio)
- Derived biometric data (pose landmarks, face blendshapes)
- Personal information (email, preferences)

## Phase 0 Baseline

Per §10 of SPEC:

### Data Minimization
- Only collect data necessary for the service
- Delete recordings per retention policy (default 90 days)

### Encryption
- TLS in transit
- Encrypted at rest (database, object storage)

### Access Control
- Authentication required for all user data
- Users can only access their own sessions
- JWT-based API authentication

### Logging
- No PII or media content in logs
- Structured JSON logging only

### Secret Management
- No secrets in git repository
- Gitleaks pre-commit scanning
- Environment variables for configuration

## Phase 2 consents (issue #37)

- `GET /me/consents` and `POST /me/consents` record granular purposes: `video_analysis`, `expression_analysis`, `keep_detailed_tracking`, plus unused-for-now `research_use` and `benchmarks`.
- Append-only rows; current state is the latest per purpose. Revocation writes `granted=false` and `revoked_at`.
- Policy texts (en, pt-BR) live in `packages/consent/v1.json`; `consents.version` is the SHA-256 of that file.
- Expression analysis and detailed tracking are off by default. Vision stages do not run without `video_analysis`. Facial movement metrics additionally require `expression_analysis`. Raw landmarks are kept only with `keep_detailed_tracking`.
- Pose/face per-second aggregates are the storage specified in SPEC §5.4 / §10.1. Raw frames are not stored as vision features.
- Issue #38 writes those aggregates as AES-256-GCM files (`STAGECOACH_ARTIFACT_KEY`). Raw landmark arrays are dropped after extraction unless `keep_detailed_tracking`.

## Compliance

- **GDPR**: Right to access, right to deletion (Phase 3)
- **LGPD**: Granular consents with specific, highlighted purpose text in pt-BR (`GET/POST /me/consents`)
- **EU AI Act**: No emotion inference; expression description only per §5, behind a separate opt-in

## Data Retention

- Media files: 90 days default (user configurable in Phase 3)
- Derived features: Deleted with session
- User accounts: Soft delete with 7-day grace period (Phase 3)

## Sub-processors

TBD - To be documented when production services are selected

## Incident Response

TBD - Phase 3

## Contact

For privacy inquiries: TBD
