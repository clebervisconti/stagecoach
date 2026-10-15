# ADR-039: In-app References, myths, and public scoring config

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 2  
**Issue:** #51

## Context

SPEC §1.2.5, §4.8, and §7.5 require every category card to cite `docs/research/sources.md`, an in-app References page with `[S#]` anchors, a Myths and limits page, and a public read-only scoring-config endpoint.

## Decision

- `GET /research/sources` parses `sources.md` (mounted at `/docs` in compose). Keys stay `S1`–`S56`.
- `GET /config/scoring/{version}` returns the YAML as JSON with `readonly: true`. Unknown versions 404. Path escape is rejected.
- Web pages: `/research`, `/research/myths` (verbatim §4.8 claims only), `/config/scoring/1.0.0`.
- Category `sources` and metric-info source keys are links to `/research#S20` (heuristics go to the myths page).
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Serve sources as a static markdown dump**  
   - ❌ No stable `#S20` anchors for category cards

2. **Let users edit scoring weights in the UI**  
   - ❌ Transparency page is read-only; new weights are a new config version

## Consequences

- Compose mounts `./docs` read-only so the API container can see `sources.md`
- BFF path segments now allow `.` so `/config/scoring/1.0.0` proxies
