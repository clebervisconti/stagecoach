# ADR-040: Observability without choosing Sentry

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 2  
**Issue:** #52

## Context

SPEC §7.1 and §10.5 ask for OpenTelemetry traces (API + workers), Prometheus metrics, per-stage debugging, and error tracking. The issue is labeled `needs-owner-decision` because Sentry is a third-party SaaS (or a self-hosted service). The owner has not chosen Sentry SaaS, self-hosted Sentry, or none.

## Decision

- Keep the existing Splunk OTel distro. API now calls `init_splunk_otel()` when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (workers already did).
- Expose Prometheus `GET /metrics`. Labels are route templates (`/api/v1/sessions/{id}`), never emails, session ids, or media paths.
- `GET /admin/analysis-costs` lists per-job stage duration and recorded `cost_usd`. Gate: `STAGECOACH_ADMIN_EMAILS`. There is no org-admin role yet (Phase 5).
- `STAGECOACH_ERROR_TRACKING` defaults to `none`. Values `sentry_saas` and `sentry_self_hosted` are accepted only as a flag that **needs an owner decision**. No Sentry SDK is installed or initialized.
- `docs/DECISIONS.md` is not edited on this branch.

## Owner decision still required

1. **Error tracking:** Sentry SaaS (paid), self-hosted Sentry (ops + possible paid), or none.
2. **Admin role:** env-list vs a real role table (v3).

## Alternatives considered

1. **Ship Sentry SaaS now**  
   - ❌ Paid service; issue says stop and ask

2. **Skip Prometheus**  
   - ❌ SPEC lists a metrics endpoint for per-stage debug

## Consequences

- Local/CI have traces off unless an OTLP collector is configured
- Cost is N/A until a stage writes `cost_usd` / `total_cost_usd` on `job_steps.metrics`
