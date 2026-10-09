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

## Compliance

- **GDPR**: Right to access, right to deletion (Phase 3)
- **LGPD**: Consent management (Phase 3)
- **EU AI Act**: No emotion inference; expression description only per §5

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
