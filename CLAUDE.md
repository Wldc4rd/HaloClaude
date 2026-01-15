# CLAUDE.md

This file provides context for Claude Code/CLI when working on this project.

## Project Overview

HaloClaude is a proxy server that allows Halo PSA (a professional services automation / IT ticketing system) to use Claude AI instead of OpenAI. Halo PSA has built-in AI features but only supports OpenAI. This proxy translates requests and adds intelligent tool calling.

## Background Context

### Why This Exists

1. Halo PSA has AI features (email generation, ticket summarization, etc.) but only supports OpenAI
2. Halo allows configuring a custom "Azure OpenAI" endpoint, which we exploit
3. The proxy accepts Azure OpenAI format requests, translates them to Claude's API format, and returns responses

### Key Technical Challenges Solved

1. **Message format mismatch**: Halo sometimes sends requests where the conversation ends with an assistant message. Claude interprets this as "prefill" and returns nothing. Solution: append a user message asking Claude to respond.

2. **Empty content**: Halo sometimes sends empty user message content (`"content": ""`). Claude's API rejects this. Solution: replace with placeholder text.

3. **Model naming**: Halo sends deployment names in the URL path. We need to map these to valid Claude model names.

## Current Architecture

Custom FastAPI proxy deployed on Azure Container Apps:

1. Receives Azure OpenAI format requests from Halo PSA
2. Fixes message format issues (empty content, assistant endings)
3. Translates to Claude API format
4. Injects Halo API tool definitions (9 tools for tickets, users, KB, etc.)
5. Executes agentic tool loop until Claude provides final response
6. Translates response back to Azure OpenAI format

## Halo PSA Context

### What Halo Sends

Halo sends requests in Azure OpenAI format to URLs like:
```
POST /openai/deployments/{deployment-name}/chat/completions?api-version=2024-02-01
```

The request body includes:
- `messages`: Array of system/user/assistant messages
- System prompt contains instructions and ticket context
- User messages contain customer emails (often as HTML)
- Assistant messages contain previous AI responses

### Halo's API

Halo has a REST API at `https://{instance}.halopsa.com/api/`:
- Authentication: OAuth2 Client Credentials flow
- Endpoints for tickets, users, clients, assets, KB articles, etc.
- API docs: https://halopsa.com/apidoc/

Key endpoints we'll use:
- `GET /tickets/{id}` - Get ticket details
- `GET /tickets/{id}/actions` - Get ticket history/actions
- `GET /users/{id}` - Get user info
- `GET /clients/{id}` - Get company info
- `GET /search/tickets` - Search tickets
- `GET /KBArticle` - Search knowledge base
- `GET /asset/{id}` - Get asset details

## Code Guidelines

### Style
- Python 3.11+ with type hints
- FastAPI for the web framework
- httpx for async HTTP requests
- Pydantic for data validation
- Follow existing code patterns

### Error Handling
- Log errors but don't expose internal details to Halo
- Return valid Azure OpenAI format errors when possible
- Gracefully handle Halo API failures (proceed without tool results)

### Testing
- Use pytest with pytest-asyncio
- Mock Halo API responses
- Test the message fixing logic thoroughly

## Key Files

- `main.py` - FastAPI app with the main endpoint
- `proxy/translator.py` - Converts between Azure OpenAI and Claude formats
- `proxy/message_fixer.py` - Fixes malformed message arrays
- `halo/client.py` - Halo API client with OAuth token management
- `halo/tools.py` - Claude tool definitions for Halo resources
- `agent/executor.py` - Runs the agentic loop (Claude → tools → Claude → ...)

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...      # Claude API key
HALO_API_URL=https://xxx.halopsa.com  # Halo instance URL
HALO_CLIENT_ID=xxx                # Halo API app client ID
HALO_CLIENT_SECRET=xxx            # Halo API app client secret
LITELLM_MASTER_KEY=xxx            # Proxy authentication key
LOG_LEVEL=INFO                    # Logging level
```

## Deployment

Currently deployed on Azure Container Apps:
- Resource group: `rg-haloclaude`
- Container app: `haloclaude-proxy`
- Container registry: `haloclauderegistrysoundit`
- Endpoint: `haloclaude-proxy.ashysky-0dacd66d.westus.azurecontainerapps.io`

## Azure CLI Setup

The local environment uses Todyl SASE which performs SSL inspection. Azure CLI requires a custom CA bundle to work.

**CA Bundle Location:** `C:\Users\CharlieCoutts\.azure\certs\ca-bundle.pem`

**Always use the wrapper script for Azure CLI commands:**
```bash
bash /c/Users/CharlieCoutts/.azure/az-wrapper.sh <command>
```

Example:
```bash
bash /c/Users/CharlieCoutts/.azure/az-wrapper.sh containerapp logs show --name haloclaude-proxy --resource-group rg-haloclaude --tail 50
```

The wrapper sets `REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE` environment variables automatically.

## Common Tasks

### Adding a New Halo Tool

1. Add the tool definition to `halo/tools.py`
2. Implement the API call in `halo/client.py`
3. Add the handler in `agent/executor.py`
4. Test with a mock response
5. Document in README.md

### Debugging Issues

1. Check Azure Container Apps logs:
   ```bash
   bash /c/Users/CharlieCoutts/.azure/az-wrapper.sh containerapp logs show --name haloclaude-proxy --resource-group rg-haloclaude --tail 100
   ```
2. Enable debug logging: Set `LOG_LEVEL=DEBUG` env var on the container app
3. Check Halo's AI logs in Configuration → Integrations → AI → Logs

### Testing Locally

```bash
# Send a test request
curl -X POST http://localhost:4000/openai/deployments/claude-sonnet-4-5/chat/completions?api-version=2024-02-01 \
  -H "Content-Type: application/json" \
  -H "api-key: your-master-key" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

## Links

- [Halo API Documentation](https://halopsa.com/apidoc/)
- [Claude API Documentation](https://docs.anthropic.com/claude/reference/messages_post)
- [Azure OpenAI API Reference](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
- [LiteLLM Documentation](https://docs.litellm.ai/)
