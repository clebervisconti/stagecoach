# ADR-080: Zod 4.6.7 for GHSA-mrhx-c7xc-m3w5

**Date:** 2026-10-23
**Status:** Accepted

## Context

`npm audit --omit=dev --audit-level=high` fails on `zod` below 4.6.6 (GHSA-mrhx-c7xc-m3w5). An array schema with no length cap records a validation issue for every failing element, and a large input can exhaust memory. The web app depends on `zod` directly at `^3.23.0`, which resolved to 3.25.76. That package is the only copy in the tree. `eslint-plugin-react-hooks` and `zod-validation-error` peer-depend on `zod@^3.25.0 || ^4.0.0` and load `zod/v4`. No application, API, or worker source imports zod.

## Decision

- Depend on `zod@^4.6.7` in `apps/web`. The lockfile resolves a single `zod@4.6.7`. Both peers dedupe onto that copy. `zod/v4` remains an export, so the hooks plugin keeps its current import.
- Do not add an `npm audit` ignore, an override, or a second nested copy.
- Leave Zod 3 call-site migration unused. A search of the repo found no `zod` import, no `errorMap`, no `.default()` / `.optional()` chain, and no `z.string().email()`. Zod 4 still ships those methods: `z.string().email()` is deprecated in favour of `z.email()`, a schema-level error map wins over the one passed to `.parse()`, and a `.default()` inside `.optional()` is applied when the key is missing.

## Alternatives considered

1. **Stay on Zod 3 and ignore the advisory**
   - The advisory has no 3.x fix. An ignore would leave the production dependency vulnerable.

2. **`npm audit fix --force`**
   - The suggested fix also downgrades `@splunk/otel-web` to 0.1.1. That is unrelated and breaking. This change only bumps zod.

## Consequences

- Production audit no longer reports a high zod finding. Moderate OpenTelemetry findings in `@splunk/otel-web` stay below the CI high threshold.
- The next code that imports `zod` gets the Zod 4 API, including the default and error-map changes above.
