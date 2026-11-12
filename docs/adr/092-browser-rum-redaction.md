# ADR-092: Splunk browser RUM, redacted, and left off

**Date:** 2026-11-12
**Status:** Accepted
**Phase:** 1.0 prep

## Context

Server traces already go to the Cyberlabs collector with `service.name=stagecoach` (`OTEL_SERVICE_NAME` on the web, API, and worker). Browser RUM was installed and left uninitialized until URL and header redaction existed. The init in `apps/web/components/rum.tsx` sent only realm, token, application name, and deployment environment.

On 11 Nov 2026 Cleber accepted moderate CVE-2026-54285 and asked for browser RUM on Stagecoach with the privacy corrections: "Sim, usa RUM também no 3dGorilla, no Bearminds e no Stagecoach, com as correções de privacidade." The same day he said to update the privacy policy and not add a consent notice: "Basta atualizar a política de privacidade, sem aviso de consentimento."

`@splunk/otel-web` 3.2.0 bundles `@opentelemetry/core` 1.30.1. CVE-2026-54285 is unbounded memory use while parsing W3C baggage, fixed in core 2.8.0. npm audit reports it as moderate (GHSA-8988-4f7v-96qf). `npm audit fix --force` would replace 3.2.0 with 0.1.1. There is no supported 3.2.x upgrade that moves this package onto core 2.8.0.

## Decision

- Keep `@splunk/otel-web` 3.2.0, bundled from npm. Do not load the agent from a CDN. Do not add the session replay package or initialize a session recorder. `sessionReplay` is not set.
- `applicationName` is `stagecoach`, matching the collector `service.name` already used by the web, API, and worker. Realm is `us1`. `deploymentEnvironment` is `production`. `beaconEndpoint` is `https://rum-ingest.us1.signalfx.com/v1/rumotlp`. `exporter.otlp` is true. Persistence is `localStorage` (no cookie from this agent).
- `user.trackingMode` is `noTracking`. Do not set `enduser.id` or `user.id`. Do not capture form fields. `privacy.maskAllText` is true.
- Before any span is exported, redact the full URL, document title, session id, media path, email addresses, and transcript text. Query strings and fragments are stripped from exported URLs. A poisoned value of any of those kinds must not appear in exported attributes. Do not send raw presentation content, recordings, or coaching transcripts.
- Do Not Track and Global Privacy Control skip initialization. There is no consent banner, and collection is not blocked on an acceptance click. The public notice is `/privacy`, in the app's English and pt-BR copy, and `docs/PRIVACY.md` states the same limits.
- The committed token stays empty. A missing or blank `NEXT_PUBLIC_SPLUNK_RUM_TOKEN` skips initialization and must not break the page. Tony holds the token and injects it at image build time, through the existing empty `NEXT_PUBLIC_SPLUNK_RUM_TOKEN` build argument, only when Cleber says go. This change does not rewrite compose, the env file, the Dockerfile, or the LION runner, and it does not deploy.
- CI keeps `npm audit --omit=dev --audit-level=high` (high and critical fail). The moderate core finding stays visible. A guardrail fails the build if session replay is enabled or a non-empty RUM token is committed.

## Alternatives considered

- Turn RUM on in this change by committing a token. The token stays with Tony until an explicit deploy go.
- Add a consent banner before any beacon. Cleber asked for a policy update and no consent notice.
- Upgrade past core 1.30.1 inside the 3.2.0 line. No such release exists. Downgrading the agent to silence the audit would drop the current RUM API.
- Send the raw `location.href`, document title, or session id and rely on Splunk's backend redaction. Stagecoach redaction has to happen before export.

## Consequences

- With an empty token the browser makes no RUM request.
- A later deploy that injects the token exports redacted OTLP to the us1 beacon under `service.name` `stagecoach`. Session replay still cannot be turned on by the committed config.
- Moderate CVE-2026-54285 remains until a future agent release supports core 2.8.0 or newer. High and critical production advisories still fail CI.
