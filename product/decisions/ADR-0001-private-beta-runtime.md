# ADR-0001: Private-beta runtime and authentication boundary

**Date:** 2026-10-10  
**Status:** Accepted

## Context

The repository has an Auth.js email flow but no production SMTP/database adapter, while the API incorrectly assumes Auth.js emits a directly verifiable HS256 token. The first deployment must be secure and usable without introducing a paid identity service.

## Decision

- Cloudflare Access is the production user-authentication boundary.
- In private-beta mode, the Next.js BFF maps the Access-protected deployment to one configured beta identity.
- Browser requests do not call FastAPI directly. Server-side route handlers authenticate the web request and mint a short-lived HS256 BFF token containing issuer, audience, subject, email, `iat`, `nbf`, and `exp`.
- FastAPI pins HS256 and validates issuer, audience, timestamps, and the email claim.
- Local development can use the same private-beta mode on loopback only.
- The API and worker share a private media volume; only the Next.js service is exposed through the tunnel.

## Alternatives

1. Finish Auth.js magic links now: rejected because production SMTP and a persistent Auth.js adapter are not provisioned.
2. Expose FastAPI to the browser with a long-lived API key: rejected because it creates a replayable browser secret.
3. Run the site without authentication: rejected because uploaded presentation media is sensitive.

## Consequences

- The private beta is single-user and depends on Cloudflare Access policy correctness.
- A later multi-user release must replace the fixed beta identity with a verified Access identity/JWT or a persistent OIDC/Auth.js flow.
- No credential is committed. `AUTH_SECRET` and Cloudflare material come from Keychain-backed deployment configuration.
