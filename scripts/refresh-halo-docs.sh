#!/bin/bash
# refresh-halo-docs.sh — Download and process the Halo PSA OpenAPI spec
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs"

mkdir -p "$DOCS_DIR"

echo "Downloading full Halo API spec..."
curl -s "https://soundit.halopsa.com/api/swagger/v2/swagger.json" > "$DOCS_DIR/halo-api-full.json"

echo "Processing spec..."
python "$REPO_ROOT/scripts/process-halo-spec.py" "$DOCS_DIR"

echo "Done."
ls -lh "$DOCS_DIR"/halo-api-*
