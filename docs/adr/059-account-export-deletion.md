# ADR-059: Zip data export and 7-day account deletion

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #67 (second slice; D10 Resend is ADR-058)

## Context

SPEC §7.5 / §10.3 require `POST /me/export` (zip of JSON + 24 h media links) and `DELETE /me` (7-day grace, then hard delete + confirmation email + audit). Session delete and the Resend adapter already exist. This slice finishes the account-level rights.

## Decision

- **Export** builds a zip in-process: `user`, `sessions`, `scores` (category + overall), `evidence`, `transcripts`, `plans` (talk plans + goals), `consents`, and `media_links`. Links are HMAC-signed (`purpose=export`) with a 24 h TTL against `AUTH_SECRET`. No live S3 in CI; the link is verified by `GET /sessions/{id}/media`.
- **Deletion** writes a `DeletionRequest` with `scope=account` and `verification.due_at` seven days out. `deleted_at` is **not** set at request time so `get_current_user` still works during the grace period. A scheduled email is sent immediately; the confirmation email is sent on finalize.
- Finalize is `process_due_deletions` plus admin `POST /admin/account-deletions/finalize`. Sessions use the existing prefix helpers; leftover `users/{id}/` objects are removed; the user row is hard-deleted (cascades plans, goals, consents, tokens). Audit rows hold counts only.
- Settings exposes export / delete / cancel. `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Soft-delete (`deleted_at`) at request time**  
   - ❌ The caller could not sign in to cancel; `get_current_user` filters `deleted_at IS NULL`

2. **Celery-only finalize**  
   - ❌ The analysis worker does not import API models cleanly; admin + service function is testable

3. **Live S3 presign in the zip**  
   - ❌ CI has no MinIO; HMAC links match the existing playback pattern

## Consequences

- D10 (Resend or console) delivers the scheduled and confirmation mail. Bodies and tokens are never logged.
- Backup copies may linger for the documented backup window after hard delete.
- Sentry / KMS / region remain owner decisions.
