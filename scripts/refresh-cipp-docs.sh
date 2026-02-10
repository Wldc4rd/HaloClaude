#!/bin/bash
# refresh-cipp-docs.sh — Fetch CIPP API endpoints from GitHub and generate docs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs/CIPP"

mkdir -p "$DOCS_DIR"

echo "Fetching CIPP-API endpoint list from GitHub..."

# Get the full recursive tree from the CIPP-API repo
gh api repos/KelvinTegelaar/CIPP-API/git/trees/master?recursive=1 \
  --jq '.tree[] | select(.path | endswith(".ps1")) | select(.path | contains("HTTP Functions")) | .path' \
  > "$DOCS_DIR/raw-endpoints.txt"

ENDPOINT_COUNT=$(wc -l < "$DOCS_DIR/raw-endpoints.txt")
echo "Found $ENDPOINT_COUNT endpoint files"

echo "Processing endpoints..."
python "$REPO_ROOT/scripts/process-cipp-endpoints.py" "$DOCS_DIR"

# Clean up temp file
rm -f "$DOCS_DIR/raw-endpoints.txt"

echo "Done."
ls -lh "$DOCS_DIR"/api-endpoints.md
