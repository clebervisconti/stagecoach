# ADR-036: PDF export via Playwright Chromium

**Date:** 2026-10-14  
**Status:** Accepted  
**Phase:** 2

## Context

Issue #49 / SPEC §6.8, §7.5, §8.9. The report exports as a 4–8 page PDF that matches the web report. Charts stay SVG. Keyframes replace video. The transcript is off unless the user ticks include transcript. A visual snapshot test compares the print view to the live report.

## Decision

- `pipeline/pdf_export.py` builds print HTML from `report.json` (and optional `transcript.json`). Playwright Chromium prints A4 PDF. No new scoring models.
- `POST /sessions/{id}/export/pdf` enqueues `tasks.export_pdf`. `GET /exports/{id}` and `/file` are ownership-checked via `meta.json` under `MEDIA_ROOT/exports/{id}`.
- The web print route `/sessions/{id}/print` reuses the same report components (summary, radar, insights, categories). Playwright E2E snapshots that view against the on-screen report score.
- LLM provider code is unchanged.

## Alternatives considered

1. **WeasyPrint / ReportLab**  
   - ❌ SPEC names Playwright Chromium so SVG and print CSS match the web

2. **Worker fetches the authenticated Next.js report URL**  
   - ❌ Extra auth hop; print HTML is generated from the same report JSON

3. **Always include the transcript**  
   - ❌ SPEC: only when the user ticks include transcript

## Consequences

- Worker images install Playwright Chromium (Apache-2.0 / BSD) for the export task
- Unit tests mock Chromium; the visual snapshot runs in web E2E where Chromium already exists
- `docs/DECISIONS.md` is not edited on this branch
