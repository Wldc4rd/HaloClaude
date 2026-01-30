Refresh the local copy of the Halo PSA API documentation.

Run the refresh script:
```
bash scripts/refresh-halo-docs.sh
```

This downloads the live OpenAPI spec from the Halo instance and creates two files:
- `docs/halo-api-full.json` — Complete OpenAPI spec
- `docs/halo-api-core.json` — Condensed spec with only the endpoints we commonly use (Tickets, Actions, Clients, Users, Assets, KB, Agents, Contracts)

Use the core spec as a reference when implementing new Halo API integrations. Read the full spec if you need endpoints not in the core set.
