# Product Changelog

## [Unreleased]

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
