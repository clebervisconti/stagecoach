# ADR-038: Multi-provider LLM settings (xAI default)

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 2

## Context

Owner decision of 14 October 2026: keep xAI (Grok) as the default LLM and add a Settings → AI providers menu. Users may point analysis at a local OpenAI-compatible endpoint (for example LM Studio serving Gemma on TIGER), Anthropic Claude, OpenAI, Google Gemini, or any custom OpenAI-compatible URL. Cloud vendors other than the default must warn that data leaves the machine. API keys must never live in the repo or in user-submitted settings.

## Decision

- `LLMClient` stays provider-neutral. Adapters: OpenAI-compatible (`xai`, `openai`, `gemini`, `local`, `custom`) and Anthropic Messages (`anthropic`).
- Default remains `xai` (`llm.yaml` `default_provider` and user `llm_settings.provider`).
- Keys resolve only from environment / secret manager (`XAI_API_KEY` / `LLM_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`, `CUSTOM_LLM_API_KEY`). Settings JSON is rejected if it contains key/secret/token fields.
- Settings store `{provider, base_url, model}` on the user. The worker writes `llm_settings.json` beside the job (still no keys).
- The web panel lists the six options. Non-default cloud choices (and custom URLs that are not loopback) show a “data leaves this machine” alert.
- Unit tests inject `StandinTransport`. They never open a socket. The previous optional live test path is not used.

## Alternatives considered

1. **Keep xAI only**  
   - ❌ Owner asked for local Gemma/LM Studio and other vendors

2. **Let users paste API keys in the browser**  
   - ❌ Keys would sit in the DB and in browser storage

3. **Call vendors from the Next.js process**  
   - ❌ Analysis already owns `LLMClient`; the worker is the right place

## Consequences

- Local loopback endpoints (LM Studio) do not show the leave-machine warning
- Missing cloud keys keep LLM stages N/A, same as today
- `docs/DECISIONS.md` is not edited on this branch
