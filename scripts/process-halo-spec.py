"""
Process the Halo PSA OpenAPI spec into efficient reference files.

Outputs:
  halo-api-index.md       — Lightweight endpoint index (paths, methods, params, response types)
  halo-api-core-paths.json  — Path definitions for commonly used endpoints
  halo-api-core-schemas.json — Only schemas referenced by core paths
"""

import json
import re
import sys
from pathlib import Path


# Endpoints we commonly use (singular and plural, case-insensitive)
CORE_PATTERN = re.compile(
    r"^/(Ticket|Action|Client|User|Asset|KnowledgeBase|Agent|Contract|KBArticle)",
    re.IGNORECASE,
)


def collect_refs(obj: object) -> set[str]:
    """Recursively collect all $ref schema names from a JSON structure."""
    refs = set()
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            # Extract schema name from "#/components/schemas/FooBar"
            if ref.startswith("#/components/schemas/"):
                refs.add(ref.split("/")[-1])
        for v in obj.values():
            refs |= collect_refs(v)
    elif isinstance(obj, list):
        for item in obj:
            refs |= collect_refs(item)
    return refs


def resolve_all_refs(schema_names: set[str], all_schemas: dict) -> dict:
    """Resolve schema names and all their transitive $ref dependencies."""
    resolved = {}
    queue = list(schema_names)
    seen = set()
    while queue:
        name = queue.pop()
        if name in seen or name not in all_schemas:
            continue
        seen.add(name)
        schema = all_schemas[name]
        resolved[name] = schema
        # Find nested refs
        for ref_name in collect_refs(schema):
            if ref_name not in seen:
                queue.append(ref_name)
    return resolved


def build_index(spec: dict) -> str:
    """Build a markdown index of all endpoints."""
    lines = [
        "# Halo PSA API Endpoint Index",
        "",
        f"Generated from OpenAPI spec: {spec.get('info', {}).get('title', 'Halo API')} "
        f"v{spec.get('info', {}).get('version', '?')}",
        "",
        "---",
        "",
    ]

    paths = spec.get("paths", {})
    for path_key in sorted(paths.keys()):
        path_def = paths[path_key]
        lines.append(f"## `{path_key}`")
        lines.append("")

        for method in ["get", "post", "put", "patch", "delete"]:
            if method not in path_def:
                continue
            op = path_def[method]
            summary = op.get("summary", "")
            lines.append(f"### {method.upper()}{('  — ' + summary) if summary else ''}")
            lines.append("")

            # Parameters
            params = op.get("parameters", [])
            if params:
                lines.append("**Parameters:**")
                lines.append("")
                lines.append("| Name | In | Type | Required | Description |")
                lines.append("|------|----|------|----------|-------------|")
                for p in params:
                    name = p.get("name", "?")
                    loc = p.get("in", "?")
                    required = "Yes" if p.get("required") else ""
                    desc = p.get("description", "").replace("\n", " ").replace("|", "\\|")
                    # Get type from schema
                    schema = p.get("schema", {})
                    ptype = schema.get("type", schema.get("$ref", "").split("/")[-1] or "?")
                    if schema.get("format"):
                        ptype += f" ({schema['format']})"
                    lines.append(f"| `{name}` | {loc} | {ptype} | {required} | {desc} |")
                lines.append("")

            # Request body
            body = op.get("requestBody", {})
            if body:
                content = body.get("content", {})
                for ctype, cdef in content.items():
                    ref = cdef.get("schema", {}).get("$ref", "")
                    schema_name = ref.split("/")[-1] if ref else "?"
                    lines.append(f"**Request Body** ({ctype}): `{schema_name}`")
                    lines.append("")

            # Response
            responses = op.get("responses", {})
            for status, rdef in responses.items():
                content = rdef.get("content", {})
                for ctype, cdef in content.items():
                    ref = cdef.get("schema", {}).get("$ref", "")
                    schema_name = ref.split("/")[-1] if ref else "inline"
                    lines.append(f"**Response {status}** ({ctype}): `{schema_name}`")
                    lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    docs_dir = Path(sys.argv[1])
    full_path = docs_dir / "halo-api-full.json"

    with open(full_path) as f:
        spec = json.load(f)

    all_paths = spec.get("paths", {})
    all_schemas = spec.get("components", {}).get("schemas", {})

    # 1. Build full index
    index_md = build_index(spec)
    (docs_dir / "halo-api-index.md").write_text(index_md, encoding="utf-8")
    print(f"  Index: {len(all_paths)} endpoints -> halo-api-index.md")

    # 2. Extract core paths
    core_paths = {k: v for k, v in all_paths.items() if CORE_PATTERN.search(k)}
    core_paths_doc = {"info": spec.get("info", {}), "paths": core_paths}
    with open(docs_dir / "halo-api-core-paths.json", "w") as f:
        json.dump(core_paths_doc, f, indent=2)
    print(f"  Core paths: {len(core_paths)} endpoints -> halo-api-core-paths.json")

    # 3. Extract only schemas referenced by core paths
    ref_names = collect_refs(core_paths)
    resolved = resolve_all_refs(ref_names, all_schemas)
    with open(docs_dir / "halo-api-core-schemas.json", "w") as f:
        json.dump(resolved, f, indent=2)
    print(f"  Core schemas: {len(resolved)} of {len(all_schemas)} schemas -> halo-api-core-schemas.json")


if __name__ == "__main__":
    main()
