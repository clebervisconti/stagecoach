# LLM Client Package

Provider-neutral LLM client with structured output support for Stage Coach analysis pipeline.

## Overview

Per ADR-007, this package provides:
- Clean, provider-neutral interface for LLM calls
- Strict JSON Schema structured outputs
- Token usage and cost tracking
- VCR-style cassettes for deterministic testing
- Support for multiple providers (xAI Grok initially)

## Usage

### Basic Usage

```python
from services.analysis.llm import LLMClient

# Initialize client (reads LLM_API_KEY from environment)
client = LLMClient()

# Generate structured output
response = client.generate_structured(
    prompt_id="message_v1",
    inputs={
        "context_type": "keynote",
        "segments": [...],
        "audience_desc": "C-suite executives"
    },
    schema=message_v1_schema  # JSON Schema
)

# Access validated data
core_message = response.data["core_message"]
level = response.data["level"]

# Check usage and cost
print(f"Tokens: {response.usage.total_tokens}")
print(f"Cost: ${response.usage.cost_usd:.4f}")
```

### Cost Tracking

```python
# At the start of each analysis
client.reset_cost_tracking()

# Make multiple LLM calls
response1 = client.generate_structured(...)
response2 = client.generate_structured(...)

# Total cost is automatically tracked
print(f"Total cost: ${client.total_cost:.4f}")

# Cost ceiling is enforced (raises LLMCostExceededError)
```

### Cassettes (Deterministic Testing)

Cassettes record LLM responses for deterministic CI tests without requiring an API key.

```python
# In tests: cassettes are enabled by default
client = LLMClient(use_cassettes=True)

# First call: makes live request and saves cassette
response = client.generate_structured(prompt_id, inputs, schema)

# Subsequent calls with same inputs: loads from cassette
response = client.generate_structured(prompt_id, inputs, schema)
```

Cassettes are saved in `tests/fixtures/llm_cassettes/` and keyed by hash of (prompt_id, inputs, schema).

### Skip Live Tests When Key Is Absent

```python
import os
import pytest

@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY not set - skipping live test"
)
def test_live_api():
    client = LLMClient(use_cassettes=False)
    # ...
```

## Configuration

Configuration is in `services/analysis/config/llm.yaml`:

- **Providers**: xAI (Grok) is configured initially; interface supports adding OpenAI, Anthropic, etc.
- **Models**: Model IDs, capabilities, and per-token prices
- **Model assignments**: Default model per prompt type
- **Cost ceiling**: Per-analysis cost limit (raises error if exceeded)
- **Timeouts and retries**: Exponential backoff for rate limits and transient errors

## Provider Support

### xAI (Grok)

- **Base URL**: `https://api.x.ai/v1` (OpenAI-compatible API)
- **Models**: `grok-beta`, `grok-2-1212`
- **Structured outputs**: Uses `response_format` with `json_schema` and `strict: true`
- **API key**: Set `LLM_API_KEY` environment variable

### Adding New Providers

1. Implement `BaseLLMProvider` in `llm/providers/`
2. Add provider config to `llm.yaml`
3. Update `LLMClient._create_provider()` factory method

## Error Handling

```python
from services.analysis.llm import (
    LLMAuthError,          # Invalid or missing API key
    LLMRateLimitError,     # Rate limit exceeded (auto-retried)
    LLMTimeoutError,       # Request timeout (auto-retried)
    LLMCostExceededError,  # Cost ceiling exceeded
    LLMValidationError,    # Response doesn't match schema
    LLMError,              # Base class
)
```

## Privacy and Logging

Per ADR-007 and §10:
- **Never log prompts with personal content in production** (`log_prompts: false`)
- **Never log full responses in production** (`log_responses: false`)
- **Always log token usage and costs** (`log_usage: true`, `log_costs: true`)
- **Never send raw video to the LLM** (enforced in pipeline stages)

## Testing

```bash
# Run tests with cassettes (no API key needed)
pytest tests/llm/

# Run tests including live API calls (requires LLM_API_KEY)
LLM_API_KEY=your_key pytest tests/llm/
```

## Cost Estimates

Based on config pricing (verify with xAI):
- Input: $5 per 1M tokens
- Output: $15 per 1M tokens

Typical analysis (10-min talk):
- Transcript: ~1,500 words → ~2,000 input tokens
- LLM calls: 5-7 prompts (outline, message, story, etc.)
- Total input: ~15,000 tokens → $0.075
- Total output: ~5,000 tokens → $0.075
- **Estimated cost per analysis: ~$0.15**

Cost ceiling is set to $0.50 per analysis.

## Dependencies

- `requests`: HTTP client for API calls
- `jsonschema`: Response validation
- `pyyaml`: Config loading
- `pydantic`: Type validation (future)

## Future Enhancements

- [ ] Prompt template loading from `prompts/` directory
- [ ] Support for other providers (OpenAI, Anthropic, Ollama)
- [ ] Streaming responses for long-form content
- [ ] Caching at the provider level (not just cassettes)
- [ ] Better error messages with retry suggestions
