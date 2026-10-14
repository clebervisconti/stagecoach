# ADR-037: Retention sweeper, lifecycle backstop, envelope encryption

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 2

## Context

Issue #50 / SPEC §10.1, §10.3, §7.3, §10.5. Retention is enforced by object-storage lifecycle rules plus a nightly job that cross-checks `media_assets.retention_until`. Derived biometric JSON needs application-level envelope encryption. KMS vendor is an owner decision.

## Decision

- Users pick `after_analysis`, `days_30` (default), or `until_delete` in settings. Upload and job-completion write `retention_until` from that choice.
- `tasks.retention_sweeper` runs on Celery beat (03:17 UTC). It deletes expired original / playback / leftover ephemeral objects and their DB rows. An integration test advances a fake clock.
- `audio16k` and the analysis proxy are unlinked when the analysis job reaches a terminal state.
- `expression_metrics.json` is SCENC2: a random DEK encrypts the JSON; the DEK is wrapped with a local KEK (`STAGECOACH_KEK` or `STAGECOACH_ARTIFACT_KEY`). Pose/face parquet stays SCENC1. Readers decrypt on load; plaintext fixtures still parse.
- `infra/object-storage-lifecycle.json` documents MinIO/S3 backstop rules. They are not applied in CI (minio profile skipped).
- KMS wrapping is a typed placeholder only. LLM provider code is unchanged.

## Alternatives considered

1. **S3 lifecycle alone**  
   - ❌ Cannot honor `until_delete` or per-user 30-day clocks stored in the DB

2. **Always use a cloud KMS in this PR**  
   - ❌ Owner decision pending; local KEK is enough for private beta

3. **Keep biometric JSON in plaintext and encrypt only parquet**  
   - ❌ SPEC §10.5 asks for envelope encryption of sensitive JSON

## Consequences

- Reports remain after originals expire; playback follows the same user policy except `after_analysis`, which keeps playback so the session is still reviewable
- `docs/DECISIONS.md` is not edited on this branch (sibling-PR convention)
