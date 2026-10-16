# ADR-058: D10 — Resend transactional email

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #67  
**Owner decision:** 2026-10-16 (D10)

## Context

Verification and password-reset mail used `app/emailing.py` with a console stand-in. Production sending needed a provider. The owner chose Resend on its free tier. Domain authentication (SPF/DKIM) for `cybersphere.com.br` is a Cyberlabs DNS change, not an agent change.

## Decision

- Add a Resend adapter behind the existing `send_email` abstraction. Call `POST https://api.resend.com/emails` with `RESEND_API_KEY` and `STAGECOACH_EMAIL_FROM` from env/secrets only.
- Official SDK is MIT (permissive). We still use the REST API so retry/backoff and mocks stay in-repo and `requirements.txt` does not grow.
- Console stand-in remains the default when the key is unset, or when `EMAIL_PROVIDER=console`.
- `verify_email` and `reset_password` have plain-text and HTML templates.
- Retry with backoff on 429/5xx and transport errors. Logs never include bodies or tokens.
- Domain setup is documented in `docs/email.md`. This PR does not change Cloudflare DNS.
- `docs/DECISIONS.md` is not edited on this branch.

Zip export and 7-day account deletion stay the rest of #67; they are not invented here beyond giving deletion-confirmation a provider to use later.

## Alternatives considered

1. **Add the official `resend` SDK**  
   - ✅ MIT  
   - ❌ Extra dep + harder to inject retry/mocks than a one-function poster

2. **Keep console-only until a paid plan**  
   - ❌ Owner chose the free tier now

3. **Let the agent write SPF/DKIM in Cloudflare**  
   - ❌ Cyberlabs applies DNS; this repo only documents the records

## Consequences

- Prod mail leaves the machine once Cyberlabs sets the two secrets and verifies the domain.
- Tests mock the poster; CI has no Resend key and makes no live calls.
- Sentry / KMS / region remain owner decisions.
