"""
HaloClaude Proxy - Main FastAPI Application

A proxy server that enables Halo PSA to use Claude AI for ticket responses,
summaries, and AI-powered features with intelligent tool calling.
"""

import asyncio
import logging
from fastapi import BackgroundTasks, FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import anthropic

from config import get_settings
from proxy.translator import AzureOpenAITranslator
from proxy.message_fixer import MessageFixer
from halo.client import HaloClient
from halo.tools import get_halo_tools
from agent.executor import AgentExecutor
from mcp_server import mcp, set_halo_client

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting HaloClaude Proxy")

    # Initialize clients
    app.state.halo_client = HaloClient(
        base_url=settings.halo_api_url,
        client_id=settings.halo_client_id,
        client_secret=settings.halo_client_secret,
    )

    # Initialize NinjaRMM client if enabled
    app.state.ninja_client = None
    if settings.ninja_enabled:
        from ninja import NinjaClient, set_ninja_client
        app.state.ninja_client = NinjaClient(
            base_url=settings.ninja_api_url,
            client_id=settings.ninja_client_id,
            client_secret=settings.ninja_client_secret,
            scope=settings.ninja_scope,
        )
        set_ninja_client(app.state.ninja_client)
        logger.info("NinjaRMM integration enabled")

    # Initialize Mesh Email Security client if enabled
    app.state.mesh_client = None
    if settings.mesh_enabled:
        from mesh import MeshClient, set_mesh_client
        app.state.mesh_client = MeshClient(
            base_url=settings.mesh_api_url,
            api_key=settings.mesh_api_key,
        )
        set_mesh_client(app.state.mesh_client)
        logger.info("Mesh Email Security integration enabled")

    # Initialize CIPP client if enabled
    app.state.cipp_client = None
    if settings.cipp_enabled:
        from cipp import CippClient, set_cipp_client
        app.state.cipp_client = CippClient(
            base_url=settings.cipp_api_url,
            tenant_id=settings.cipp_tenant_id,
            client_id=settings.cipp_client_id,
            client_secret=settings.cipp_client_secret,
            application_id=settings.cipp_application_id,
        )
        set_cipp_client(app.state.cipp_client)
        logger.info("CIPP integration enabled")

    app.state.translator = AzureOpenAITranslator()
    app.state.message_fixer = MessageFixer()
    app.state.agent_executor = AgentExecutor(
        halo_client=app.state.halo_client,
        anthropic_api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        context_injection_enabled=settings.context_injection_enabled,
        context_cache_ttl=settings.context_cache_ttl,
        sop_kb_search_term=settings.sop_kb_search_term,
        sop_kb_filter_tag=settings.sop_kb_filter_tag,
        max_sop_articles=settings.max_sop_articles,
        max_sop_article_length=settings.max_sop_article_length,
        max_contract_doc_length=settings.max_contract_doc_length,
        ninja_client=app.state.ninja_client,
        mesh_client=app.state.mesh_client,
        cipp_client=app.state.cipp_client,
    )

    # Set up MCP server with shared HaloClient
    set_halo_client(app.state.halo_client)

    # Run MCP session manager
    async with mcp.session_manager.run():
        yield

    # Cleanup
    if app.state.cipp_client:
        await app.state.cipp_client.close()
    if app.state.mesh_client:
        await app.state.mesh_client.close()
    if app.state.ninja_client:
        await app.state.ninja_client.close()
    await app.state.halo_client.close()
    logger.info("Shutting down HaloClaude Proxy")


app = FastAPI(
    title="HaloClaude Proxy",
    description="Proxy server enabling Halo PSA to use Claude AI",
    version="0.1.0",
    lifespan=lifespan,
)

# Add MCP authentication middleware
if settings.entra_tenant_id and settings.entra_client_id:
    # Entra ID OAuth active — FastMCP handles token validation via BearerAuthBackend.
    # This middleware only normalizes api-key headers for backward compat.
    from mcp_server.auth import ApiKeyHeaderMiddleware
    app.add_middleware(ApiKeyHeaderMiddleware)
else:
    # No Entra ID — use legacy static-key middleware
    from mcp_server.auth import MCPAuthMiddleware
    app.add_middleware(MCPAuthMiddleware)

# Mount MCP server. Starlette redirects /mcp → /mcp/ (307) but some MCP
# clients don't follow redirects, so a middleware rewrites the path.
_mcp_app = mcp.streamable_http_app()
app.mount("/mcp", _mcp_app)


@app.middleware("http")
async def rewrite_mcp_trailing_slash(request: Request, call_next):
    """Rewrite /mcp to /mcp/ to avoid Starlette's 307 redirect."""
    if request.url.path == "/mcp":
        request.scope["path"] = "/mcp/"
    return await call_next(request)


@app.get("/.well-known/oauth-protected-resource/mcp")
@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata():
    """RFC 9728 Protected Resource Metadata for the MCP endpoint."""
    if not settings.entra_tenant_id or not settings.entra_client_id:
        raise HTTPException(status_code=404, detail="OAuth not configured")

    return {
        "resource": f"api://{settings.entra_client_id}",
        "authorization_servers": [
            f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0"
        ],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [
            f"api://{settings.entra_client_id}/MCP.Access",
        ],
    }


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata():
    """Proxy Entra ID's OAuth authorization server metadata.

    Claude (March 2025 spec) expects this on the MCP server itself.
    We fetch and return Entra ID's OpenID Connect metadata, remapping
    field names to match RFC 8414 where needed.
    """
    if not settings.entra_tenant_id:
        raise HTTPException(status_code=404, detail="OAuth not configured")

    import httpx
    entra_url = (
        f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0"
        f"/.well-known/openid-configuration"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(entra_url)
        resp.raise_for_status()
        metadata = resp.json()

    # Rewrite authorization and token endpoints to point to our proxies.
    # This ensures our scope-rewriting logic runs, so Claude requests
    # our app's scope instead of defaulting to Microsoft Graph.
    base = settings.public_base_url.rstrip("/")
    metadata["authorization_endpoint"] = f"{base}/authorize"
    metadata["token_endpoint"] = f"{base}/token"
    return metadata


@app.get("/authorize")
async def oauth_authorize_redirect(request: Request):
    """Redirect to Entra ID's authorization endpoint.

    Claude (March 2025 spec) sends the authorize request to the MCP server.
    We redirect to Entra ID, rewriting the scope from 'claudeai' to the
    actual Entra resource scope.
    """
    from starlette.responses import RedirectResponse

    if not settings.entra_tenant_id or not settings.entra_client_id:
        raise HTTPException(status_code=404, detail="OAuth not configured")

    # Build Entra authorize URL with the original query params
    params = dict(request.query_params)

    # Claude sends scope=claudeai — replace with our actual scope
    scope = params.get("scope", "")
    if "claudeai" in scope or not scope:
        params["scope"] = f"api://{settings.entra_client_id}/MCP.Access offline_access openid"

    from urllib.parse import urlencode
    entra_authorize = (
        f"https://login.microsoftonline.com/{settings.entra_tenant_id}/oauth2/v2.0/authorize"
        f"?{urlencode(params)}"
    )
    return RedirectResponse(url=entra_authorize, status_code=302)


@app.post("/token")
async def oauth_token_proxy(request: Request):
    """Proxy token requests to Entra ID.

    Claude sends the token exchange to the MCP server (March 2025 spec).
    We forward it to Entra ID's token endpoint.
    """
    if not settings.entra_tenant_id:
        raise HTTPException(status_code=404, detail="OAuth not configured")

    import httpx
    form_data = await request.form()
    params = dict(form_data)

    # Ensure scope is set for the token exchange
    if "scope" not in params or "claudeai" in params.get("scope", ""):
        params["scope"] = f"api://{settings.entra_client_id}/MCP.Access offline_access openid"

    entra_token_url = (
        f"https://login.microsoftonline.com/{settings.entra_tenant_id}/oauth2/v2.0/token"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(entra_token_url, data=params)
        resp_json = resp.json()
        if resp.status_code != 200:
            logger.warning(f"Token proxy: Entra error status={resp.status_code}")
        return JSONResponse(status_code=resp.status_code, content=resp_json)


@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "haloclaude-proxy"}


@app.post("/openai/deployments/{deployment}/chat/completions")
async def chat_completions(
    deployment: str,
    request: Request,
    api_key: str = Header(alias="api-key"),
):
    """
    Main endpoint that accepts Azure OpenAI format requests,
    translates them to Claude, executes any tool calls, and
    returns the response in Azure OpenAI format.
    """
    # Verify API key
    if api_key != settings.litellm_master_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        # Parse request body
        body = await request.json()
        logger.debug(f"Received request for deployment: {deployment}")
        logger.debug(f"Request body: {body}")
        
        # Extract messages
        messages = body.get("messages", [])
        
        # Fix any message format issues
        messages = request.app.state.message_fixer.fix_messages(messages)
        
        # Get tools
        tools = get_halo_tools()
        if request.app.state.ninja_client:
            from ninja import get_ninja_tools
            tools = tools + get_ninja_tools()
        if request.app.state.mesh_client:
            from mesh import get_mesh_tools
            tools = tools + get_mesh_tools()
        if request.app.state.cipp_client:
            from cipp import get_cipp_tools
            tools = tools + get_cipp_tools()

        # Execute agent loop (handles tool calls)
        response = await request.app.state.agent_executor.run(
            messages=messages,
            tools=tools,
        )
        
        # Translate response to Azure OpenAI format
        azure_response = request.app.state.translator.to_azure_openai(response)
        
        logger.debug(f"Returning response: {azure_response}")
        return JSONResponse(content=azure_response)
        
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error: {e.status_code} - {e.message}")

        # Map Anthropic errors to user-friendly messages
        if e.status_code == 529:
            user_message = "The AI service is temporarily busy. Please try again in a moment."
        elif e.status_code == 503:
            user_message = "The AI service is temporarily unavailable. Please try again shortly."
        elif e.status_code == 429:
            user_message = "Too many requests to the AI service. Please wait a moment and try again."
        elif e.status_code == 401:
            user_message = "AI service authentication error. Please contact your administrator."
        else:
            user_message = "An error occurred with the AI service. Please try again."

        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "message": user_message,
                    "type": "api_error",
                    "code": str(e.status_code)
                }
            }
        )

    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "An unexpected error occurred. Please try again.",
                    "type": "internal_error",
                    "code": "500"
                }
            }
        )


@app.post("/webhook/triage", status_code=202)
async def webhook_triage(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Header(alias="api-key"),
):
    """
    Trigger the triage pipeline for a ticket.

    Called by Halo runbooks (button clicks or scheduled).
    Runs asynchronously and writes results back to Halo.
    """
    if api_key != settings.litellm_master_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not settings.triage_enabled:
        raise HTTPException(status_code=503, detail="Triage pipeline is disabled")

    body = await request.json()
    ticket_id = body.get("ticket_id")

    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")

    try:
        ticket_id = int(ticket_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ticket_id must be an integer")

    logger.info(f"Triage webhook received for ticket {ticket_id}")

    background_tasks.add_task(
        _run_pipeline_background,
        ticket_id=ticket_id,
        mode="triage",
        app=request.app,
    )

    return {"status": "accepted", "ticket_id": ticket_id}


@app.post("/webhook/review", status_code=202)
async def webhook_review(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Header(alias="api-key"),
):
    """
    Trigger the review pipeline for a ticket.

    Called by Halo runbooks (e.g. "no actions for X days") or on demand.
    Runs asynchronously and writes results back to Halo.
    """
    if api_key != settings.litellm_master_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not settings.review_enabled:
        raise HTTPException(status_code=503, detail="Review pipeline is disabled")

    body = await request.json()
    ticket_id = body.get("ticket_id")

    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")

    try:
        ticket_id = int(ticket_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ticket_id must be an integer")

    logger.info(f"Review webhook received for ticket {ticket_id}")

    background_tasks.add_task(
        _run_pipeline_background,
        ticket_id=ticket_id,
        mode="review",
        app=request.app,
    )

    return {"status": "accepted", "ticket_id": ticket_id}


# Limit concurrent pipeline executions to avoid Halo API rate limits
# (700 requests per rolling 5-minute window)
_pipeline_semaphore = asyncio.Semaphore(2)


async def _run_pipeline_background(
    ticket_id: int, app: FastAPI, mode: str = "triage",
):
    """Background task wrapper for the ticket pipeline."""
    from triage import run_ticket_pipeline

    async with _pipeline_semaphore:
        try:
            result = await run_ticket_pipeline(
                ticket_id=ticket_id,
                halo_client=app.state.halo_client,
                ninja_client=app.state.ninja_client,
                anthropic_api_key=settings.anthropic_api_key,
                model=settings.triage_model,
                mode=mode,
                review_model=settings.review_model if mode == "review" else None,
                sop_kb_search_term=settings.sop_kb_search_term,
                sop_kb_filter_tag=settings.sop_kb_filter_tag,
                max_sop_articles=settings.max_sop_articles,
                max_sop_article_length=settings.max_sop_article_length,
                max_contract_doc_length=settings.max_contract_doc_length,
                mesh_client=app.state.mesh_client,
                cipp_client=app.state.cipp_client,
            )
            logger.info(f"Ticket pipeline ({mode}) complete for ticket {ticket_id}: {result}")
        except Exception as e:
            logger.exception(f"Ticket pipeline ({mode}) failed for ticket {ticket_id}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)
