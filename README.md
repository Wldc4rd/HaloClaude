# HaloClaude Proxy

A proxy server that enables Halo PSA to use Claude AI instead of OpenAI for ticket responses, summaries, and AI-powered features. Includes intelligent tool calling that gives Claude access to Halo's API for richer context.

## Features

- **Automatic Context Injection**: Pre-fetches ticket details, history, user info, company data, and linked assets from Halo and injects into Claude's context automatically
- **Azure OpenAI API Translation**: Accepts requests in Azure OpenAI format and translates them to Claude's API
- **Message Format Fixing**: Handles edge cases where Halo sends malformed requests (empty messages, conversations ending with assistant turns)
- **Halo API Tools**: Gives Claude the ability to fetch additional context from Halo (ticket history, user info, company details, KB articles)
- **Agentic Loop**: Automatically executes tool calls and returns results to Claude until a final response is generated

## Architecture

```
┌─────────────┐      ┌─────────────────────────────────────┐      ┌─────────────┐
│             │      │          HaloClaude Proxy           │      │             │
│   Halo PSA  │─────►│                                     │─────►│   Claude    │
│             │      │  • Azure OpenAI → Claude translation│      │    API      │
│             │◄─────│  • Tool definitions injection       │◄─────│             │
│             │      │  • Tool execution (Halo API calls)  │      │             │
│   Halo API  │◄────►│  • Response formatting              │      └─────────────┘
│             │      │                                     │
└─────────────┘      └─────────────────────────────────────┘
```

## Status

✅ **Fully Operational** - Deployed on Azure Container Apps with all features working:

- Automatic context injection (ticket, history, user, client, assets)
- Azure OpenAI → Claude API translation
- Message format fixing (empty content, assistant endings)
- Halo API OAuth authentication
- All 9 tool definitions for Halo resources
- Agentic tool execution loop
- Support for Claude Sonnet and Opus models

## Prerequisites

- Python 3.11+
- Anthropic API key
- Halo PSA instance with API access
- Azure Container Apps (for deployment) or local Docker

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `ANTHROPIC_MODEL` | Claude model to use (default: `claude-sonnet-4-5-20250929`) |
| `HALO_API_URL` | Your Halo instance URL (e.g., `https://yourcompany.halopsa.com`) |
| `HALO_CLIENT_ID` | Halo API application Client ID |
| `HALO_CLIENT_SECRET` | Halo API application Client Secret |
| `LITELLM_MASTER_KEY` | Secret key to protect the proxy endpoint |
| `LOG_LEVEL` | Logging level (default: `INFO`) |
| `CONTEXT_INJECTION_ENABLED` | Enable automatic context injection (default: `true`) |
| `CONTEXT_CACHE_TTL` | Cache duration for context in seconds (default: `300`) |

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/Wldc4rd/HaloClaude.git
cd HaloClaude

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Run the proxy
python -m uvicorn main:app --reload --port 4000
```

### Docker

```bash
docker build -t haloclaude .
docker run -p 4000:4000 --env-file .env haloclaude
```

### Azure Container Apps

See [docs/azure-deployment.md](docs/azure-deployment.md) for detailed deployment instructions.

## Halo PSA Configuration

1. Go to **Configuration** → **Integrations** → **AI**
2. Select **Own Azure OpenAI Connection**
3. Configure:
   - **Endpoint**: Your proxy URL (e.g., `https://your-proxy.azurecontainerapps.io`)
   - **API Key**: Your `LITELLM_MASTER_KEY`
   - **API Version**: `2024-02-01`
   - **Default Azure OpenAI Deployment**: `claude-sonnet-4-5` or `claude-opus-4-5`

### Halo API Application Setup

1. Go to **Configuration** → **Integrations** → **Halo API**
2. Create a new API application
3. Note the **Client ID** and **Client Secret**
4. Ensure the associated **Agent** has permissions to:
   - View tickets
   - View users/clients
   - View assets
   - View knowledge base articles

## Automatic Context Injection

When a request contains a ticket ID (e.g., "Ticket #12345" in the system prompt), the proxy automatically:

1. **Parses** the ticket ID from the system prompt
2. **Fetches** in parallel from Halo API:
   - Ticket details (summary, status, priority, dates)
   - Ticket history (all actions/notes)
   - User information (contact details, location)
   - Client/company data (SLA, notes)
   - Linked assets (device specs, serial numbers)
3. **Injects** formatted context into Claude's system prompt
4. **Caches** results for 5 minutes to avoid repeated API calls

This gives Claude comprehensive context without needing to make tool calls, resulting in faster and more informed responses.

## Available Tools

Claude also has access to these tools for fetching additional Halo context:

| Tool | Description |
|------|-------------|
| `get_ticket` | Get full details and history of a ticket |
| `get_user` | Get user information and contact details |
| `get_user_tickets` | Get other tickets for a user |
| `get_client` | Get company/client information |
| `get_client_tickets` | Get recent tickets for a company |
| `get_asset` | Get asset/device details |
| `search_tickets` | Search for tickets by keyword |
| `search_kb` | Search the knowledge base |
| `get_kb_article` | Get full knowledge base article content |

## Project Structure

```
HaloClaude/
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration management
├── proxy/
│   ├── translator.py       # Azure OpenAI ↔ Claude translation
│   └── message_fixer.py    # Message format corrections
├── halo/
│   ├── auth.py             # Halo OAuth token management
│   ├── client.py           # Halo API client
│   └── tools.py            # Tool definitions for Claude
├── context/
│   ├── parser.py           # Ticket ID extraction from prompts
│   ├── fetcher.py          # Parallel data fetching from Halo
│   ├── formatter.py        # Context formatting for injection
│   └── injector.py         # Orchestrates context injection
├── agent/
│   └── executor.py         # Tool execution loop
├── tests/
│   └── test_message_fixer.py
├── docs/
│   └── azure-deployment.md
├── .env.example
├── requirements.txt
├── Dockerfile
├── CLAUDE.md               # Context for Claude Code
└── README.md
```

## License

MIT License - see [LICENSE](LICENSE) for details.
