"""
HaloClaude Proxy - Main FastAPI Application

A proxy server that enables Halo PSA to use Claude AI for ticket responses,
summaries, and AI-powered features with intelligent tool calling.
"""

import logging
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from config import get_settings
from proxy.translator import AzureOpenAITranslator
from proxy.message_fixer import MessageFixer
from halo.client import HaloClient
from halo.tools import get_halo_tools
from agent.executor import AgentExecutor

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
    app.state.translator = AzureOpenAITranslator()
    app.state.message_fixer = MessageFixer()
    app.state.agent_executor = AgentExecutor(
        halo_client=app.state.halo_client,
        anthropic_api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        context_injection_enabled=settings.context_injection_enabled,
        context_cache_ttl=settings.context_cache_ttl,
    )
    
    yield
    
    # Cleanup
    await app.state.halo_client.close()
    logger.info("Shutting down HaloClaude Proxy")


app = FastAPI(
    title="HaloClaude Proxy",
    description="Proxy server enabling Halo PSA to use Claude AI",
    version="0.1.0",
    lifespan=lifespan,
)


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
        
        # Get Halo tools
        tools = get_halo_tools()
        
        # Execute agent loop (handles tool calls)
        response = await request.app.state.agent_executor.run(
            messages=messages,
            tools=tools,
        )
        
        # Translate response to Azure OpenAI format
        azure_response = request.app.state.translator.to_azure_openai(response)
        
        logger.debug(f"Returning response: {azure_response}")
        return JSONResponse(content=azure_response)
        
    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": "500"
                }
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)
