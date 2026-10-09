# JSON Schemas

Canonical JSON Schema definitions for all analysis artifacts and API contracts.

## Schemas

- **analysis_result.v1.json** - Complete analysis output (§7.7 in SPEC)
- **talk_plan.v1.json** - Talk-prep coach plan structure (Phase 3)
- **transcript.v1.json** - Word-level transcript format
- **events.v1.json** - SSE progress event types

## Type Generation

TypeScript and Python types are auto-generated from these schemas:

```bash
# Generate TypeScript types
npm run generate:types

# Generate Python pydantic models
python scripts/generate_pydantic.py
```

Generated files:
- `generated/typescript/` → used by apps/web and services/api
- `generated/python/` → used by services/analysis

## Validation

All schemas are validated against JSON Schema Draft 2020-12.

```python
import jsonschema
from pathlib import Path

schema = json.loads(Path("analysis_result.v1.json").read_text())
jsonschema.validate(instance=data, schema=schema)
```

## Version Policy

- Schema URIs include version: `https://example.com/stagecoach/schemas/analysis_result.v1.json`
- Breaking changes require a new major version
- Old analysis results can always be validated against their schema version
