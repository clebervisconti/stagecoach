# Transactional email (D10 — Resend)

Owner decision 2026-10-16: production mail is **Resend**, free tier. This document is for Cyberlabs to apply. **Do not change DNS from this repository or from a cloud agent.**

## Secrets (env / host secret store only)

| Variable | Required for Resend | Notes |
|---|---|---|
| `RESEND_API_KEY` | yes | Dashboard API key. Never commit. |
| `STAGECOACH_EMAIL_FROM` | yes | Verified From, e.g. `Stage Coach <noreply@cybersphere.com.br>` |
| `EMAIL_PROVIDER` | no | `console` (default) forces the stand-in even if a key is present |
| `STAGECOACH_PUBLIC_URL` | no | Used in verify/reset links; falls back to `NEXTAUTH_URL` |

When `RESEND_API_KEY` is unset, the API keeps the console / in-memory stand-in. CI never calls `api.resend.com`.

## Domain verification on cybersphere.com.br (Cloudflare DNS)

Cyberlabs applies these in the Cloudflare DNS UI for `cybersphere.com.br`. The agent must not create or edit records.

1. In Resend → Domains, add `cybersphere.com.br` (or the `stagecoach` subdomain you will send from).
2. Resend shows SPF, DKIM, and (optional) DMARC values.
3. In Cloudflare DNS, add those records **exactly** as Resend lists them:
   - **SPF** — TXT on `@` or the sending subdomain. Merge with any existing `v=spf1` (do not create a second SPF). Include Resend's `include:` and keep `~all` / `-all` as counsel prefers.
   - **DKIM** — CNAME pair(s) Resend issues (often `resend._domainkey` → Resend). Proxy status: **DNS only** (grey cloud).
   - **DMARC** (recommended) — TXT on `_dmarc` once SPF+DKIM pass. Start with `p=none`.
4. Wait for Resend to show the domain as verified.
5. Set `STAGECOACH_EMAIL_FROM` to an address on that domain and `RESEND_API_KEY` on the host.

Return-path / MX for bounce handling stays whatever Resend documents for the free tier. Do not point the corporate MX at Resend.

## What the app sends

| Purpose | Template |
|---|---|
| `verify_email` | text + HTML, token + link to `/sign-in` |
| `reset_password` | text + HTML, token + link to `/sign-in` |

Logs record `purpose`, `provider`, HTTP status, and attempt number only. Bodies and tokens are not logged.

## Licence

The official Python SDK is MIT. This repo calls the public REST API (`POST https://api.resend.com/emails`) so retry/backoff and test doubles stay in-tree and no extra dependency is added.
