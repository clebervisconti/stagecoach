# ADR-092: Practice loop and account quotas

**Date:** 2026-11-13
**Status:** Accepted

## Context

Delivery modes, layout review, and screen-flow scoring already shipped in ADR-061 through ADR-091. What is still missing is a way to practice one skill, see a weekly plan, and compare two takes of the same talk. A public self-serve launch is still gated. Cloudflare Access, Resend, Apple, counsel review, KMS, and moving speech recognition off this host stay owner decisions.

## Decision

- Add drills, a weekly plan, rehearsal series on a talk plan, transcript correction, and PPTX deck review. These notes do not replace the session score.
- Audio and video drills are transcribed and scored for the drill's target signals. Accent is not scored.
- Quotas default to 2 GB stored, one running analysis, and 180 minutes in the current month. `QUOTA_STORAGE_BYTES`, `QUOTA_ACTIVE_JOBS`, and `QUOTA_MONTHLY_SECONDS` override them. Minutes come from original media duration plus queued drill time.
- `GET /api/v1/account/readiness` reports which launch gates are set. It does not turn them on. `SELF_SERVE_OPEN` stays unset.
- The product does not score emotion, accent, or whether the content is factually true.

## Consequences

Migration `015_practice_loop` must run before the API writes drill attempts. Online delivery behaviour is unchanged.
