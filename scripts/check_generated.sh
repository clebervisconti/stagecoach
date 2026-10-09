#!/bin/bash
# CI check: verify generated code is up to date
set -e

echo "Checking if generated types are up to date..."

# Save current generated files
TEMP_DIR=$(mktemp -d)
if [ -f "services/api/app/schemas/analysis_result.py" ]; then
    cp services/api/app/schemas/analysis_result.py "$TEMP_DIR/analysis_result.py.old"
fi

# Regenerate
bash scripts/generate_types.sh > /dev/null 2>&1

# Compare
if [ -f "$TEMP_DIR/analysis_result.py.old" ]; then
    if ! diff -q services/api/app/schemas/analysis_result.py "$TEMP_DIR/analysis_result.py.old" > /dev/null 2>&1; then
        echo "❌ Generated types are stale. Run 'bash scripts/generate_types.sh' and commit the result."
        rm -rf "$TEMP_DIR"
        exit 1
    fi
fi

rm -rf "$TEMP_DIR"
echo "✓ Generated types are up to date"
