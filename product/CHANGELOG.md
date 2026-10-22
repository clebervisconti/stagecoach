# Product Changelog

## [Unreleased]

### Added

- Draft spec for online and recorded session analysis at `docs/online-sessions/SPEC.md`. Phases O0–O6 and owner decisions OD-1–OD-10 are on the roadmap and backlog. The feature flag stays off. Stage scoring is unchanged.

## [0.4.0] - 2026-10-17

### Added

- Content analysis runs inside the upload job. If the language model is down, message and structure categories stay N/A.
- Talk-prep regeneration writes a core message, structure, time budget, cut list, and rehearsal plan from the existing generators.
- Report Objectives tab with planned section times and a personal-baseline badge after three sessions in the same language. The badge does not replace the population score.

### Notes

- Production remains the 0.2.0 private beta until the owner cuts a release and closes the gates in `deploy/README.md`.

## [0.2.0] - 2026-10-10

### Added

- Private-beta web flow for creating sessions, uploading media, tracking analysis, reviewing an evidence-linked partial audio/text report, and deleting all session data.
- Production deployment definition for LION and `stagecoach.cybersphere.com.br`.
- Product, release, security, UAT, and rollback artifacts.

### Security

- Cloudflare Access at the public edge.
- Loopback/private-network service exposure.
- Bounded streaming uploads, generated storage names, ownership checks, and path-containment checks.
- No credentials in source; production values load from Keychain-backed deployment environment.
