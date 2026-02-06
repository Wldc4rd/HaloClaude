"""
HaloClaude Proxy - Main FastAPI Application

A proxy server that enables Halo PSA to use Claude AI for ticket responses,
summaries, and AI-powered features with intelligent tool calling.
"""

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
from mcp_server.auth import MCPAuthMiddleware

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
    )

    # Set up MCP server with shared HaloClient
    set_halo_client(app.state.halo_client)

    # Run MCP session manager
    async with mcp.session_manager.run():
        yield

    # Cleanup
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
app.add_middleware(MCPAuthMiddleware)

# Mount MCP server at /mcp
app.mount("/mcp", mcp.streamable_http_app())


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
        _run_triage_background,
        ticket_id=ticket_id,
        app=request.app,
    )

    return {"status": "accepted", "ticket_id": ticket_id}


async def _run_triage_background(ticket_id: int, app: FastAPI):
    """Background task wrapper for the triage pipeline."""
    from triage import run_triage_pipeline

    try:
        result = await run_triage_pipeline(
            ticket_id=ticket_id,
            halo_client=app.state.halo_client,
            ninja_client=app.state.ninja_client,
            anthropic_api_key=settings.anthropic_api_key,
            model=settings.triage_model,
            sop_kb_search_term=settings.sop_kb_search_term,
            sop_kb_filter_tag=settings.sop_kb_filter_tag,
            max_sop_articles=settings.max_sop_articles,
            max_sop_article_length=settings.max_sop_article_length,
            max_contract_doc_length=settings.max_contract_doc_length,
        )
        logger.info(f"Triage pipeline complete for ticket {ticket_id}: {result}")
    except Exception as e:
        logger.exception(f"Triage pipeline failed for ticket {ticket_id}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)
