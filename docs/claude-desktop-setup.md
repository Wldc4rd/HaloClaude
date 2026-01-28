# Claude Desktop MCP Setup

Connect Claude Desktop to Halo PSA via the HaloClaude MCP server. This gives Claude Desktop access to tickets, users, clients, assets, and knowledge base articles.

## Prerequisites

- [Node.js](https://nodejs.org/) (for `npx` / `mcp-remote`)
- Claude Desktop installed
- HaloClaude proxy deployed (or running locally)

## Setup

### 1. Create a wrapper batch file

Claude Desktop on Windows has quoting issues when passing arguments through `cmd.exe`. A wrapper batch file avoids this.

Create `%APPDATA%\Claude\haloclaude-mcp.bat`:

```bat
@echo off
npx -y mcp-remote https://haloclaude-proxy.ashysky-0dacd66d.westus.azurecontainerapps.io/mcp/mcp --header "Authorization: Bearer YOUR_LITELLM_MASTER_KEY"
```

Replace `YOUR_LITELLM_MASTER_KEY` with your actual key.

For **local development**, use:

```bat
@echo off
npx -y mcp-remote http://localhost:4000/mcp/mcp --allow-http --header "Authorization: Bearer YOUR_LITELLM_MASTER_KEY"
```

### 2. Configure Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "haloclaude": {
      "command": "C:\\Users\\YOUR_USERNAME\\AppData\\Roaming\\Claude\\haloclaude-mcp.bat",
      "env": {
        "NODE_EXTRA_CA_CERTS": "C:\\path\\to\\ca-bundle.pem"
      }
    }
  }
}
```

- Replace `YOUR_USERNAME` with your Windows username.
- The `NODE_EXTRA_CA_CERTS` entry is only needed if your network uses SSL inspection (e.g., Todyl SASE, Zscaler, etc.). Point it at a CA bundle that includes your inspection proxy's certificate. Remove this field if you don't use SSL inspection.

### 3. Restart Claude Desktop

Fully quit and reopen Claude Desktop. The "haloclaude" server should appear in the MCP servers list.

## Troubleshooting

### Check the logs

Logs are at: `%APPDATA%\Claude\logs\mcp-server-haloclaude.log`

### Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` | SSL inspection intercepting traffic | Add `NODE_EXTRA_CA_CERTS` env var pointing to your CA bundle |
| `'C:\Program' is not recognized` | Space in Node.js path breaks `cmd.exe` argument parsing | Use the wrapper batch file approach above |
| `Invalid Host header` (421) | MCP SDK DNS rebinding protection | Already disabled in the server; ensure you're hitting the correct `/mcp/mcp` path |
| `Unauthorized` (401) | Wrong API key | Check the Bearer token in your batch file matches `LITELLM_MASTER_KEY` |
| Server spinning / no response | mcp-remote connection issue | Test the endpoint directly: `curl https://your-proxy/mcp/mcp` |

### Test the endpoint manually

```bash
curl -X POST https://haloclaude-proxy.ashysky-0dacd66d.westus.azurecontainerapps.io/mcp/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_LITELLM_MASTER_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Available Tools

Once connected, Claude Desktop can use these Halo PSA tools:

| Tool | Description |
|------|-------------|
| `get_ticket` | Get ticket details |
| `get_ticket_actions` | Get ticket history and notes |
| `create_ticket` | Create a new ticket |
| `update_ticket` | Update ticket fields |
| `close_ticket` | Close/resolve a ticket |
| `create_ticket_note` | Add or update a note on a ticket |
| `search_tickets` | Search tickets by keyword |
| `get_user` | Get user details |
| `get_user_tickets` | Get tickets for a user |
| `get_client` | Get client/company details |
| `get_client_tickets` | Get tickets for a client |
| `get_asset` | Get asset/device details |
| `search_kb` | Search knowledge base |
| `get_kb_article` | Get a knowledge base article |
