# ADR-057: D9 — email+password and Sign in with Apple

**Date:** 2026-10-16  
**Status:** Accepted. The Cloudflare Access bypass in Consequences is removed by [ADR-083](083-app-owned-auth.md) (2026-10-24). This file stays the record of password and Apple sign-in.  
**Phase:** 3  
**Issue:** #68  
**Owner decision:** 2026-10-15 (D9)

## Context

SPEC §3.1 originally listed magic links plus Google / Microsoft OAuth. The owner decided the only sign-in options are (a) email plus password and (b) Sign in with Apple. D10 (production email provider) is still open. Magic links were never finished (Auth.js `providers` was empty; SMTP is not provisioned).

## Decision

- **Passwords** live on the API: argon2id (`argon2-cffi`), minimum 10 characters, offline common-breach denylist, per-IP/email token bucket, lockout after 5 failures for 15 minutes.
- **Email verification and password reset** use `app/emailing.py`. The stand-in is `EMAIL_PROVIDER=console` (print + in-memory outbox). No paid provider.
- **Sign in with Apple** is OIDC with PKCE and nonce. The API validates the ID token against Apple's JWKS (or `APPLE_JWKS_JSON` in tests). Private-relay addresses (`@privaterelay.appleid.com`) are stored as the account email; `apple_sub` is the stable link.
- `APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, and `APPLE_PRIVATE_KEY` are env/secrets only. The provider stays **disabled** until all four are set. Setup is in `docs/apple-signin.md`.
- **Magic-link Email provider is retired.** `/verify-request` says so. Google and Microsoft are not added.
- Tests use stand-ins: no live `appleid.apple.com` calls. Have I Been Pwned is not used (free, but not offline).
- `docs/DECISIONS.md` is not edited on this branch. CHANGELOG / `ci.yml` / i18n files stay with sibling PRs.

## Alternatives considered

1. **Keep magic links beside passwords**  
   - ❌ Two email-only flows; owner retired magic links

2. **Auth.js Apple provider only**  
   - ❌ Harder to unit-test JWKS / nonce / private relay without live Apple

3. **HIBP range API for breached passwords**  
   - ❌ Network dependency; owner asked for offline-capable

## Consequences

- Private-beta Cloudflare Access + `PRIVATE_BETA_MODE` still bypasses the form in CI.
- D10 still required before verification/reset email leaves the console stand-in.
- Google / Microsoft remain out of scope.
