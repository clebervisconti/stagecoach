# ADR-041: Report accessibility (axe-core, keyboard, captions)

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 2  
**Issue:** #53

## Context

SPEC §8.11 / §10.7 / §11.6 require WCAG 2.2 AA on the report: keyboard player and timeline, captions from the transcript, a color-blind-safe palette with patterns, and `prefers-reduced-motion`.

## Decision

- Add `@axe-core/playwright` as a **devDependency**. axe-core is MPL-2.0 (copyleft on modified axe-core files). It was already a transitive package. This is test-only, not shipped to browsers as an app feature.
- Playwright: axe on `[data-testid=report]`; keyboard-only focus on player, evidence, timeline lanes; assert `<track kind="captions">`.
- Radar and timeline use hatch patterns in addition to hue.
- Global CSS honors `prefers-reduced-motion`.
- Color-contrast axe rule stays disabled in CI (theme tokens are not yet fully audited). Serious/critical other rules must be empty.
- `docs/DECISIONS.md` is not edited on this branch.

## Licence note (flag)

Owner should confirm MPL-2.0 **test-only** axe-core is acceptable as a direct devDependency. No production license change.

## Alternatives considered

1. **Skip axe and rely on manual review**  
   - ❌ SPEC names `@axe-core/playwright`

2. **Ship a new charting library for patterns**  
   - ❌ Extra dep; SVG hatch is enough
