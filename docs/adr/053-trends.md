# ADR-053: Trends API and config-major comparability

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #64

## Context

SPEC §4.6.3 / §8.8 / §7.5: `GET /trends` returns a per-user series. Deltas are only shown when two sessions share context and scoring-config **major** version. Otherwise the UI says "not comparable" with the reason. The dashboard shows sparklines, per-metric filters, most improved, and needs attention.

## Decision

- Comparability math lives in `app/trends_service.py`. The router only loads the current user's latest job per session.
- Language and metric/category are optional filters. With no context filter, the newest session's context is the reference.
- `/trends` replaces the Phase 3 stub. Nav already had the `trends` key.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Drop incompatible sessions from the payload**  
   - ❌ AC: mark them, do not hide them

2. **Compare across scoring-config majors with a footnote**  
   - ❌ Spec: major breaks comparability

## Consequences

- Goals on this dashboard stay issue #65 (no `/goals` here).
