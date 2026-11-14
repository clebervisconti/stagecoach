# ADR-093: Invite-only registration

**Date:** 2026-11-13
**Status:** Accepted

## Context

Stage Coach's public face is the sign-in page. There is no marketing site. Open self-registration created an account for any email and told the person to read a server console when production mail was not configured. The owner decided on 13 Nov 2026 that sign-up is invite-only.

Sign in with Apple already links a verified Apple ID to an existing account (ADR-057, ADR-083). Creating a brand-new account from Apple, with no prior row, is also self-registration.

## Decision

- `POST /api/v1/auth/register` without an invite returns 403. A valid single-use invite still creates an unverified member and sends the verification mail. An invite used on an email that already has an account does not change that account and still returns the same accepted response.
- An administrator creates accounts as before (`POST /api/v1/admin/users`). That path does not need an invite. The same administrator can issue an invite (`POST /api/v1/admin/invites`). The raw invite is returned once and is not written to the audit log.
- Invites are hashed in `auth_tokens` with purpose `invite` and no user id. They expire after 7 days. Migration `016_invite_tokens` makes `auth_tokens.user_id` nullable. Apply it with `alembic upgrade head` before issuing invites.
- Sign in with Apple still signs in an account that already has that `apple_sub`, and still links a verified Apple email to an existing verified account. A new Apple account is created only when the finish request includes a valid invite. Otherwise the API returns 403 and does not insert a user.
- The sign-in page does not offer Create account unless the URL carries an invite. Sign in with Apple is shown only when the four Apple settings are present.

## Alternatives considered

- Hide Create account in the page and leave `POST /auth/register` open. The API would still accept public sign-up.
- A feature flag that turns public registration back on. The owner chose invite-only, not a switch.

## Consequences

- Existing admin-created accounts keep working, including the forced password change.
- Someone with only an Apple ID and no invite cannot create an account from the button. An administrator creates the account, or issues an invite, first.
- This change does not deploy and does not set Apple or mail secrets.
