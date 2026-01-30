#!/bin/bash
# refresh-halo-docs.sh — Download and condense the Halo PSA OpenAPI spec
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs"

mkdir -p "$DOCS_DIR"

echo "Downloading full Halo API spec..."
curl -s "https://soundit.halopsa.com/api/swagger/v2/swagger.json" > "$DOCS_DIR/halo-api-full.json"

echo "Creating condensed core spec..."
python -c "
import json, re, os

script_dir = os.path.dirname(os.path.abspath('$0'))
docs_dir = os.path.join(script_dir, '..', 'docs') if script_dir else 'docs'
# Use the same directory resolution as the shell
docs_dir = os.path.normpath(os.path.join(os.getcwd(), 'docs'))

with open(os.path.join(docs_dir, 'halo-api-full.json')) as f:
    spec = json.load(f)

pattern = re.compile(r'Tickets|Actions|Clients|Users|Assets|KnowledgeBase|Agents|Contract|KBArticle', re.IGNORECASE)
core_paths = {k: v for k, v in spec.get('paths', {}).items() if pattern.search(k)}

core = {
    'info': spec.get('info', {}),
    'paths': core_paths,
    'components': {'schemas': spec.get('components', {}).get('schemas', {})},
}

with open(os.path.join(docs_dir, 'halo-api-core.json'), 'w') as f:
    json.dump(core, f, indent=2)

print(f'  Core paths: {len(core_paths)}')
"

FULL_SIZE=$(wc -c < "$DOCS_DIR/halo-api-full.json" | tr -d ' ')
CORE_SIZE=$(wc -c < "$DOCS_DIR/halo-api-core.json" | tr -d ' ')

echo "Done."
echo "  Full spec: $DOCS_DIR/halo-api-full.json ($FULL_SIZE bytes)"
echo "  Core spec: $DOCS_DIR/halo-api-core.json ($CORE_SIZE bytes)"
