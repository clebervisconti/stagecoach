# Stage Coach Web App

Next.js 14 application (App Router) providing the user-facing interface.

## Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS + shadcn/ui (Radix primitives)
- **Charts**: Recharts for standard charts, custom SVG for timeline/radar
- **Video**: Native `<video>` with custom accessible controls
- **i18n**: next-intl (en, pt-BR)
- **Auth**: Auth.js (NextAuth) integration

## Structure

```
app/
  (marketing)/        - Landing, about, pricing
  (app)/
    sessions/         - Session list and report views
    prep/             - Talk-prep coach
    trends/           - Progress tracking
    settings/         - User settings and consents
components/
  report/             - RadarChart, CategoryCard, Timeline, etc.
  ui/                 - shadcn/ui components
lib/
  api/                - Generated OpenAPI client
```

## Development

```bash
pnpm install
pnpm dev              # Start dev server on :3000
pnpm build
pnpm test
pnpm lint
```

## Phase Status

- Phase 0: Placeholder
- Phase 1+: Implementation
