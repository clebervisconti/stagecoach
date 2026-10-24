# ADR-084: Roles and the per-user online-modes flag

**Date:** 2026-10-24
**Status:** Accepted
**Phase:** Auth

## Context

Admin was `STAGECOACH_ADMIN_EMAILS` (ADR-040). Online modes were `ONLINE_MODES_ENABLED` and an email allowlist, falling back to `PRIVATE_BETA_EMAIL` (ADR-072). The product has no shared sessions. Each account owns its talks, plans, and consents. The owner needs to add people and turn online modes on without editing the environment or the repo.

## Decision

Three roles:

| Role | What they can do |
| --- | --- |
| `admin` | Everything a member can do, plus `/admin/users` and the existing admin operations (analysis costs, finalizing due deletions). |
| `member` | Default. Owns their talks, prep, trends, consents, and export. |
| `viewer` | Read-only. GET is allowed. POST, PATCH, and DELETE are rejected except `POST /api/v1/me/export` and `POST /api/v1/auth/password`. |

There is no sharing product. `viewer` is a real seat for someone who should look and not change data. The checks are on the API. Hiding a link is not the control.

The role in the database wins. A JWT claim of `admin` does not. Changing a role, disabling an account, or revoking sessions increments `session_version`.

An admin cannot demote, disable, or delete themselves. Removing the last active admin is rejected.

Admin delete is a soft delete: `deleted_at` is set, the email becomes `deleted-{id}@users.invalid`, `apple_sub` is cleared, and sessions die. The partial unique index `uq_users_email_active` lets that address be registered again. The 7-day self-service deletion is unchanged.

Online modes are `ONLINE_MODES_ENABLED` and the per-user `online_modes` flag. An email, including an admin's, does not turn the feature on. Migration 012 does not copy the old allowlist; those addresses lived only in the environment. After deploy, an admin turns the flag on for the right accounts. `URL_INGEST_ENABLED` is unchanged.

`GET/POST/PATCH/DELETE /api/v1/admin/users` is admin-only. Create and reset return the temporary password once. Audit rows record the action, role, and an email digest. They do not record the password, the raw email, or the name.

New self-registrations and new Apple users are `member` with `online_modes` false.

## Alternatives considered

- Keep the email allowlists — they are the thing that makes a directly exposed app depend on whoever is in the environment.
- Give every admin online modes automatically — the global flag is still how the feature stays off for everyone.
- Hard-delete from the admin screen — the self-service path already has a grace period. Admin delete needs the address reusable immediately and the sessions dead immediately.
- A coach role separate from member — the app has one owner of each talk. Member is that person.

## Consequences

- ADR-072's allowlist no longer grants access. ADR-040's `STAGECOACH_ADMIN_EMAILS` gate no longer grants access.
- `GET /admin/analysis-costs` and `POST /admin/account-deletions/finalize` require `role=admin`.
- The users screen is `/admin/users`, linked in the shell only for admins. A non-admin who requests the API gets 403.
