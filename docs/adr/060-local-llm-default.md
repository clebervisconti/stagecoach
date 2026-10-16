# ADR-060: Local LM Studio (Qwen) is the default LLM

**Date:** 2026-10-16  
**Status:** Accepted  
**Phase:** 3  
**Supersedes:** ADR-038  
**Owner decision:** 2026-10-16

## Context

ADR-038 made xAI (Grok) the default and added a Settings → AI providers menu. On 16 October 2026 the owner changed the default to the local OpenAI-compatible server on TIGER (LM Studio) so the app can boot and deploy without a paid cloud key.

## Decision

- **Default provider** is `local`. Default model is `qwen/qwen3.8-27b`.
- **Base URL** comes from `LOCAL_LLM_BASE_URL` (fallback `http://127.0.0.1:1234/v1`). No API key.
- **xAI/Grok** stays in Settings but is off by default. `XAI_API_KEY` is optional. Selecting xAI without a key keeps those LLM stages N/A; it must not block process start.
- Settings default and `llm.yaml` `default_provider` both follow this.
- Cloud vendors (including xAI now that it is not the default) show the “data leaves this machine” warning. Loopback local URLs do not.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Keep xAI as default and only document LOCAL_LLM_BASE_URL**  
   - ❌ Owner asked to change the default; deploy must work without `XAI_API_KEY`

2. **Require a dummy xAI key in compose**  
   - ❌ Fake secrets hide a real boot dependency

## Consequences

- Analysis on LION talks to TIGER through `LOCAL_LLM_BASE_URL`.
- Existing user rows that stored `provider: xai` keep that choice until they change Settings.
- ADR-038 remains the source for the multi-provider menu and “no keys in settings” rule.
