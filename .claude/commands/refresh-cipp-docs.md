Refresh the local copy of the CIPP API documentation.

Run the refresh script:
```
bash scripts/refresh-cipp-docs.sh
```

This fetches the latest endpoint list from the CIPP-API GitHub repository and generates:

- `docs/CIPP/api-endpoints.md` — Complete reference of ALL CIPP API endpoints organized by category (Identity, Email-Exchange, Endpoint, Security, Teams-SharePoint, Tenant, etc.)

The script uses `gh api` to read the repository tree and extract all HTTP Function entrypoints, then processes them into a structured markdown document.

**Recommended workflow when implementing new CIPP API integrations:**
1. Read `docs/CIPP/api-endpoints.md` to find the endpoint you need
2. If you need parameter details, read the endpoint's source file from the CIPP-API repo using `gh api repos/KelvinTegelaar/CIPP-API/contents/<path>`
3. Add the new method to `cipp/client.py`, tool definition to `cipp/tools.py`, MCP registration to `cipp/mcp_tools.py`, and handler to `agent/executor.py`
