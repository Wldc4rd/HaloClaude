# HaloClaude Proxy

A proxy server that enables Halo PSA to use Claude AI instead of OpenAI for ticket responses, summaries, and AI-powered features. Includes intelligent tool calling that gives Claude access to Halo's API for richer context.

## Features

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

## Current Status

### Working (Phase 1 - LiteLLM Proxy)
- ✅ Basic proxy translating Azure OpenAI requests to Claude
- ✅ Fix for empty message content
- ✅ Fix for conversations ending with assistant messages
- ✅ Deployed on Azure Container Apps

### In Development (Phase 2 - Tool Calling)
- 🔲 Halo API authentication
- 🔲 Tool definitions for Halo resources
- 🔲 Agentic tool execution loop
- 🔲 Response caching

## Prerequisites

- Python 3.11+
- Anthropic API key
- Halo PSA instance with API access
- Azure Container Apps (for deployment) or local Docker

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `HALO_API_URL` | Your Halo instance URL (e.g., `https://yourcompany.halopsa.com`) |
| `HALO_CLIENT_ID` | Halo API application Client ID |
| `HALO_CLIENT_SECRET` | Halo API application Client Secret |
| `LITELLM_MASTER_KEY` | Secret key to protect the proxy endpoint |

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/haloclaude.git
cd haloclaude

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
   - **Default Azure OpenAI Deployment**: `claude-sonnet-4-5`

## Available Tools (Phase 2)

When Phase 2 is complete, Claude will have access to these tools:

| Tool | Description |
|------|-------------|
| `get_ticket` | Get full details and history of a ticket |
| `get_user` | Get user information and contact details |
| `get_user_tickets` | Get other tickets for a user |
| `get_client` | Get company/client information |
| `get_client_tickets` | Get recent tickets for a company |
| `search_kb` | Search the knowledge base |
| `get_asset` | Get asset/device details |
| `get_actions` | Get available actions for a ticket |

## Project Structure

```
haloclaude/
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration management
├── proxy/
│   ├── __init__.py
│   ├── translator.py       # Azure OpenAI ↔ Claude translation
│   └── message_fixer.py    # Message format corrections
├── halo/
│   ├── __init__.py
│   ├── auth.py             # Halo OAuth token management
│   ├── client.py           # Halo API client
│   └── tools.py            # Tool definitions for Claude
├── agent/
│   ├── __init__.py
│   └── executor.py         # Tool execution loop
├── tests/
│   └── ...
├── docs/
│   ├── azure-deployment.md
│   └── halo-api-reference.md
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [LiteLLM](https://github.com/BerriAI/litellm) for initial proxy functionality
- Inspired by the need to use Claude's superior reasoning in Halo PSA
