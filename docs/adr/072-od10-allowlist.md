# ADR-072: Online modes allowlist (OD-10)

**Date:** 2026-10-22
**Status:** Superseded by [ADR-084](084-roles-and-online-modes.md). Online modes are a per-user flag, not an email allowlist.
**Phase:** O1

## Context

OD-10: online modes stay behind the existing flag and are enabled only for Cleber's account until the security gate passes.

## Decision

`user_online_modes_enabled(email)` is true only when `ONLINE_MODES_ENABLED` is on **and** the email is in `ONLINE_MODES_ALLOWED_EMAILS` (comma list). If that list is empty, fall back to `PRIVATE_BETA_EMAIL`. An empty allowlist denies everyone. `/me` exposes `online_modes_enabled` so the web app can show the wizard.

## Alternatives considered

Flag-only (any signed-in user) — rejected, OD-10 is account-scoped.
Hard-code one email in the repo — rejected, the allowlist is env-only.
