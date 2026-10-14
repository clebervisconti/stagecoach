# ADR-0002: CPU ASR on LION for private beta

**Date:** 2026-10-12  
**Status:** Accepted (private beta only)

## Context

Homelab architecture keeps generation, embeddings, and speech inference on TIGER.
The private-beta MVP needs a working upload → transcript → report loop on LION,
which is the always-on web host behind `stagecoach.cybersphere.com.br`.

## Decision

Run `faster-whisper` with `ASR_MODEL=tiny` inside the Stage Coach worker
container on LION. Do not expose the worker or API on host ports. Do not run
large-v3, GPU, or live-overlay inference on LION.

## Alternatives

1. Split ASR to TIGER over the LAN: rejected for the first slice because it
   adds a second always-on dependency and a new media-transfer path.
2. Call a remote ASR API: rejected until a zero-retention commercial contract
   is approved.

## Consequences

- Private-beta transcripts are lower quality than production `large-v3`.
- A later release must move ASR to TIGER or a licensed remote API and keep
  LION as the web/BFF host only.
