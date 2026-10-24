# ADR-083: App-owned authentication without Cloudflare Access

**Date:** 2026-10-24
**Status:** Accepted
**Phase:** Auth

## Context

Production sat behind Cloudflare Access and then the app's own sign-in. `PRIVATE_BETA_MODE` skipped Auth.js and minted a BFF token for one email, so the app was not safe to expose directly. Password and Sign in with Apple already existed (ADR-057). There is no `Cf-Access-Jwt-Assertion` parser. The dependency was the beta bypass, plus email allowlists for admin and online modes.

## Decision

- The browser session stays an Auth.js JWT cookie: `httpOnly`, `SameSite=Lax`, `Secure` when `AUTH_URL` or `NEXTAUTH_URL` is `https`, 12-hour max age. Lax keeps the Apple redirect (`response_mode=query`, a GET) working. The BFF still mints a 60-second HS256 token for FastAPI. That token now carries `sv` (session version). The API rejects a missing user, a disabled user, a deleted user, and a mismatched `sv`. It no longer creates a user from the token.
- Password hashes are argon2id (m=19 MiB, t=2, p=1). New passwords are at least 10 characters, at most 200, and not on the offline breach list. A temporary password may be shorter only because `must_change_password` is set.
- Login failures — unknown email, bad password, lockout, disabled, unverified — all return 401 `Invalid email or password`. A missing account still runs a dummy verify. Lockout (5 failures, 15 minutes) stays inside that response. The token bucket (burst 5, then 1 per 5 seconds, per IP and per email digest) still returns 429, because it runs before the lookup and does not prove the account exists. Compares of token purpose use `secrets.compare_digest`.
- State-changing BFF requests require `Sec-Fetch-Site` other than `cross-site`, and an `Origin` host that matches `Host` or `X-Forwarded-Host`.
- `users.session_version` increments on password change, role change, disable, revoke, admin reset, and delete. Other browsers die. The password-change response includes a new two-minute session ticket so the current browser can refresh its cookie.
- A user with `must_change_password` can call only `POST /api/v1/auth/password`.
- Sign in with Apple still matches `apple_sub` first. A verified Apple email may link to an existing row when that row has no different `apple_sub`, is not disabled, and is not an unverified password account. Unverified local rows are not linked (that would let a squatted address inherit the Apple login). A stored email is not overwritten. New Apple users are `member`. Disabled Apple users get the same generic Apple error.
- Public registration no longer attaches a password to an existing row. It always returns `{status: accepted}`.
- Forgot password does not look up the user and does not send mail. An administrator sets a temporary password. `POST /auth/reset` remains for a token that was already issued, and it bumps `session_version`. There is no outbound reset email.
- The first admin is not in git. On the server, after migrations:

```bash
read -r BOOTSTRAP_ADMIN_EMAIL
read -rs BOOTSTRAP_ADMIN_TEMP_PASSWORD
export BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_TEMP_PASSWORD
docker compose -f docker-compose.prod.yml exec -T \
  -e BOOTSTRAP_ADMIN_EMAIL -e BOOTSTRAP_ADMIN_TEMP_PASSWORD \
  api python -m app.bootstrap_admin
unset BOOTSTRAP_ADMIN_TEMP_PASSWORD
```

The command reads those variables from the environment only. It is idempotent: missing email creates an admin with `must_change_password`; an admin who already has a password is left alone (`present`); a password-less stub is upgraded only when no active admin exists (`updated`); a member who already has a password is not taken over; a deleted row is not resurrected. Exit 2 if either variable is missing, before the database is opened. The password is never printed.

- `cf-ipcountry` is still read as an optional country hint on consent rows. It does not authenticate anyone and does not grant a role.
- Cutover order is in `deploy/README.md`: deploy this release, bootstrap the admin, sign in and change the password, verify, and only then remove Cloudflare Access. `deploy/cloudflare-private-beta.sh` stays until that step.

## Alternatives considered

- bcrypt — argon2id is already the stack and matches the OWASP parameters in ADR-057.
- A custom CSRF header on every `fetch` — too many call sites; a missed header would break production. Origin plus SameSite=Lax covers the browser.
- Emailing password resets now — no outbound mail is approved for this path. Admin reset is enough.
- Running bootstrap on process start — the temporary password would have to live in the long-running environment.
- An e2e auth bypass flag — `next start` is production mode, so a bypass could be turned on in Compose. Playwright writes an Auth.js cookie with the CI secret instead.

## Consequences

- `PRIVATE_BETA_MODE` and `PRIVATE_BETA_EMAIL` no longer sign anyone in. They are removed from the web image, Compose, and CI.
- Existing rows become `member` with `session_version` 1 and `must_change_password` false. Nobody is an admin until the bootstrap command runs.
- A user who was auto-created by the old beta bypass has no password. Bootstrap can upgrade that stub when it is the address you pass and no admin exists yet.
- Self-service registration still verifies email through the console stand-in or Resend. Login of an unverified password account is the generic 401.
