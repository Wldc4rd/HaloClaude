Refresh the local copy of the Halo PSA API documentation.

Run the refresh script:
```
bash scripts/refresh-halo-docs.sh
```

This downloads the live OpenAPI spec from the Halo instance and generates:

- `docs/halo-api-full.json` — Complete OpenAPI spec (large, use only for edge cases)
- `docs/halo-api-index.md` — Lightweight markdown index of ALL endpoints with parameters and response types. Read this first when looking up any endpoint.
- `docs/halo-api-core-paths.json` — Full path definitions for commonly used endpoints (Tickets, Actions, Clients, Users, Assets, KB, Agents, Contracts)
- `docs/halo-api-core-schemas.json` — Only the schemas referenced by core paths

**Recommended workflow when implementing Halo API integrations:**
1. Read `docs/halo-api-index.md` to find the endpoint and its parameters
2. If you need full request/response schema details, read `docs/halo-api-core-schemas.json` for the specific schema name from the index
3. If the endpoint isn't in the core set, read the relevant section from `docs/halo-api-full.json`
