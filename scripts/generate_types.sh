#!/bin/bash
# Generate TypeScript and Python types from JSON schemas
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Generating types from JSON schemas..."

# Generate Python pydantic models from JSON schemas
echo "  → Python pydantic models..."
cd "$ROOT_DIR"

# Install datamodel-code-generator if not available
if ! command -v datamodel-codegen &> /dev/null; then
    if [ ! -f "$HOME/.local/bin/datamodel-codegen" ]; then
        echo "    Installing datamodel-code-generator..."
        pip install -q "datamodel-code-generator[http]==0.25.1"
    fi
fi

# Use datamodel-codegen from PATH or ~/.local/bin
DATAMODEL_CODEGEN="datamodel-codegen"
if [ -f "$HOME/.local/bin/datamodel-codegen" ]; then
    DATAMODEL_CODEGEN="$HOME/.local/bin/datamodel-codegen"
fi

# Generate pydantic models for analysis_result schema
$DATAMODEL_CODEGEN \
  --input packages/schemas/analysis_result.v1.json \
  --output services/api/app/schemas/analysis_result.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-standard-collections \
  --use-annotated \
  --field-constraints \
  --snake-case-field \
  --target-python-version 3.11 \
  --disable-timestamp

echo "✓ Generated Python types"

# TypeScript type generation will be added when Next.js app is set up (Issue #11)
echo "  → TypeScript types (deferred to Next.js setup)"

echo ""
echo "✓ Type generation complete"
