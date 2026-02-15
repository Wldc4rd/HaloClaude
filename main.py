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

    # Initialize 1Stream client if enabled
    app.state.onestream_client = None
    if settings.onestream_enabled:
        from onestream import OneStreamClient, set_onestream_client
        app.state.onestream_client = OneStreamClient(
            base_url=settings.onestream_api_url,
            api_key=settings.onestream_api_key,
        )
        set_onestream_client(app.state.onestream_client)
        logger.info("1Stream integration enabled")

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
    if app.state.onestream_client:
        await app.state.onestream_client.close()
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

    # Log any POST requests to unexpected paths (helps debug webhook delivery)
    path = request.url.path
    if request.method == "POST" and not path.startswith(("/mcp", "/openai", "/webhook/", "/token")):
        logger.warning(
            f"Unexpected POST to {path} from {request.client.host if request.client else 'unknown'}"
        )

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


@app.post("/webhook/onestream", status_code=202)
@app.post("/webhook/onestream/", status_code=202, include_in_schema=False)
async def webhook_onestream(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    1Stream CallEnd / TranscriptionReady webhook.

    Handles two event types:
    - CallEnd: In-flight CallID (NOT the database ID). Match by extension +
      phone number + timestamp instead.
    - TranscriptionReady: Permanent database CallID. Look up directly via
      GetCallLogs.

    No API key auth — 1Stream webhooks don't support custom headers.
    """
    if not settings.onestream_enabled:
        raise HTTPException(status_code=503, detail="1Stream integration is disabled")

    raw_body = await request.body()
    logger.info(f"1Stream webhook raw payload: {raw_body[:500]}")

    body = await request.json()
    event_type = body.get("EventType", "unknown")
    logger.info(
        f"1Stream webhook: EventType={event_type}, "
        f"CallID={body.get('CallID')}, Ext={body.get('ExtensionNumber')}"
    )

    background_tasks.add_task(
        _run_onestream_transcription,
        webhook_body=body,
        app=request.app,
    )

    return {"status": "accepted", "event_type": event_type}


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


async def _run_onestream_transcription(
    webhook_body: dict,
    app: FastAPI,
):
    """Background task: look up a 1Stream call and run the transcription pipeline.

    Handles two webhook event types:
    - TranscriptionReady: CallID is the permanent database ID → direct lookup
    - CallEnd: CallID is an in-flight ID → match by extension + phone + timestamp
    """
    from mcp_server.transcribe import transcribe_call_recording
    from mcp_server.prompts import SPEAKER_CONTEXT_TEMPLATE

    onestream_client = app.state.onestream_client
    halo_client = app.state.halo_client

    event_type = webhook_body.get("EventType", "unknown")
    call_id = str(webhook_body.get("CallID", ""))
    timestamp = webhook_body.get("DateTimeStamp")

    async with _pipeline_semaphore:
        try:
            # CallEnd fires immediately — the call log / recording may not
            # be available yet. Wait a bit before searching.
            if event_type == "CallEnd":
                logger.info("1Stream: CallEnd received, waiting 30s for call log to appear")
                await asyncio.sleep(30)

            # 1. Find the call log entry (strategy depends on event type)
            if event_type == "TranscriptionReady":
                # Permanent database CallID — direct lookup
                call_log = await _find_onestream_call_by_id(
                    onestream_client, call_id, timestamp,
                )
            else:
                # CallEnd — in-flight ID, match by extension + phone + time
                call_log = await _find_onestream_call_by_metadata(
                    onestream_client, webhook_body,
                )

            if not call_log:
                logger.warning(
                    f"1Stream: No matching call found for {event_type} webhook "
                    f"(CallID={call_id}), skipping"
                )
                return

            db_call_id = call_log.get("CallID", call_id)
            logger.info(
                f"1Stream: Found call {db_call_id}: "
                f"{'Inbound' if call_log.get('Inbound') else 'Outbound'}, "
                f"{call_log.get('TalkTimeSeconds', 0)}s, "
                f"CRMTicketID={call_log.get('CRMTicketID')}"
            )

            # 2. Resolve the Halo ticket
            ticket_id = None
            crm_ticket_id = call_log.get("CRMTicketID")
            if crm_ticket_id and int(crm_ticket_id) > 0:
                ticket_id = int(crm_ticket_id)
                logger.info(f"1Stream: Using CRMTicketID={ticket_id}")
            else:
                ticket_id = await _resolve_ticket_by_phone(
                    halo_client, call_log,
                )
                if ticket_id:
                    logger.info(
                        f"1Stream: Resolved ticket {ticket_id} via phone lookup"
                    )

            if not ticket_id:
                logger.warning(
                    f"1Stream: No Halo ticket found for call {db_call_id}, skipping"
                )
                return

            # 3. Build speaker context from Halo ticket (most reliable source)
            is_inbound = call_log.get("Inbound", True)
            customer_name = None
            agent_name = None

            try:
                ticket = await halo_client.get_ticket(ticket_id)
                customer_name = ticket.get("user_name")
                agent_name = ticket.get("agent_name")
                logger.info(
                    f"1Stream: Ticket {ticket_id} — "
                    f"user={customer_name}, agent={agent_name}"
                )
            except Exception:
                logger.warning(
                    f"1Stream: Could not fetch ticket {ticket_id} for speaker context"
                )

            # Fall back to 1Stream metadata if ticket lookup failed
            if not customer_name:
                if is_inbound:
                    customer_name = call_log.get("OriginatedByName") or "Unknown Caller"
                else:
                    customer_name = call_log.get("DestinationName") or "Unknown Contact"
            if not agent_name:
                agent_name = call_log.get("ExtensionName") or "Unknown Agent"

            participants = (
                f"- **Customer/End-User**: {customer_name}\n"
                f"- **Agent (IT Technician)**: {agent_name}\n"
            )
            speaker_context = SPEAKER_CONTEXT_TEMPLATE.format(
                participants=participants,
            )

            # 4. Download the recording
            download_url = call_log.get("DownloadRecording")
            if not download_url:
                logger.warning(
                    f"1Stream: No DownloadRecording URL for call {db_call_id}"
                )
                return

            audio_bytes = await onestream_client.download_recording(download_url)

            # 5. Build call metadata for the note
            # 1Stream uses OriginatedBy/Destination instead of CallerID/Dialled
            if is_inbound:
                external_number = call_log.get("OriginatedBy")
                external_name = call_log.get("OriginatedByName")
            else:
                external_number = call_log.get("Destination")
                external_name = call_log.get("DestinationName")

            # Use the webhook's DateTimeStamp (call end time in UTC) as the note
            # datetime, since the call log's ActualEndTime can be unreliable.
            # Fall back to parsing the .NET date from the call log if no webhook ts.
            webhook_ts = webhook_body.get("DateTimeStamp")
            if webhook_ts:
                webhook_dt = _parse_onestream_timestamp(webhook_ts)
                note_datetime = webhook_dt.isoformat()
            else:
                call_end_iso = _parse_dotnet_date(call_log.get("ActualEndTime"))
                call_start_iso = _parse_dotnet_date(call_log.get("ActualStartTime"))
                note_datetime = call_end_iso or call_start_iso
            logger.info(f"1Stream: Note datetime = {note_datetime}")

            call_metadata = {
                "direction": "Inbound" if is_inbound else "Outbound",
                "caller_number": external_number,
                "caller_name": external_name or call_log.get("OriginatedByName"),
                "dialled_number": call_log.get("Destination") if not is_inbound else None,
                "extension": call_log.get("ExtensionName"),
                "datetime": note_datetime,
            }

            # 6. Run transcription pipeline
            duration_seconds = call_log.get("TalkTimeSeconds")

            result = await transcribe_call_recording(
                halo_client=halo_client,
                ticket_id=ticket_id,
                post_note=True,
                audio_bytes=audio_bytes,
                speaker_context_override=speaker_context,
                duration_override=float(duration_seconds) if duration_seconds else None,
                note_datetime=note_datetime,
                call_metadata=call_metadata,
            )

            logger.info(
                f"1Stream: Transcription complete for call {db_call_id} "
                f"→ ticket {ticket_id} ({len(result)} chars)"
            )

        except Exception as e:
            logger.exception(
                f"1Stream: Transcription failed for {event_type} "
                f"CallID={call_id}: {e}"
            )


def _parse_onestream_timestamp(timestamp: str | None):
    """Parse 1Stream webhook timestamps (e.g. '2/15/2026 8:36:26\u202fPM')."""
    from datetime import datetime

    if not timestamp:
        return datetime.utcnow()

    try:
        clean = timestamp.replace("\u202f", " ").replace("\xa0", " ").strip()
        for fmt in (
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %H:%M",
        ):
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                continue
        return datetime.fromisoformat(clean.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        logger.warning(f"1Stream: Could not parse timestamp '{timestamp}', using now")
        return datetime.utcnow()


def _parse_dotnet_date(value: str | None) -> str | None:
    """Parse a .NET JSON date like '/Date(1769954587000-0500)/' to ISO 8601.

    Returns an ISO 8601 string (e.g. '2026-02-15T12:36:27-05:00') or None.
    """
    if not value:
        return None

    import re
    from datetime import datetime, timezone, timedelta

    m = re.search(r"/Date\((\d+)([+-]\d{4})?\)/", value)
    if not m:
        return None

    epoch_ms = int(m.group(1))
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)

    # Apply the timezone offset if present
    if m.group(2):
        offset_str = m.group(2)
        offset_hours = int(offset_str[:3])
        offset_mins = int(offset_str[0] + offset_str[3:5])
        tz = timezone(timedelta(hours=offset_hours, minutes=offset_mins))
        dt = dt.astimezone(tz)

    return dt.isoformat()


def _extract_phone_from_webhook(webhook_body: dict) -> str | None:
    """Extract the external phone number from a CallEnd webhook payload.

    For inbound: FromPhone is the external number (clean digits)
    For outbound: ToPhone is the external number (clean digits)
    The trunk side looks like 'Wexternalline.52: 10000 on Wprovider...'
    """
    import re

    from_phone = webhook_body.get("FromPhone", "")
    to_phone = webhook_body.get("ToPhone", "")

    # The trunk side contains 'Wexternalline' or 'Wprovider'
    # The real phone number is the other side
    for phone in (from_phone, to_phone):
        if not phone:
            continue
        # Skip trunk-detail strings
        if "Wexternalline" in phone or "Wprovider" in phone:
            continue
        # Extract digits (strip +, spaces, dashes)
        digits = re.sub(r"[^\d]", "", phone)
        if len(digits) >= 7:
            return digits

    return None


async def _find_onestream_call_by_id(
    client,
    call_id: str,
    timestamp: str | None,
) -> dict | None:
    """Find a call log entry by permanent database CallID (TranscriptionReady)."""
    from datetime import timedelta

    dt = _parse_onestream_timestamp(timestamp)
    call_id_str = str(call_id).strip()

    for window_minutes in (5, 15, 60):
        start = (dt - timedelta(minutes=window_minutes)).strftime("%-m/%-d/%Y %H:%M")
        end = (dt + timedelta(minutes=window_minutes)).strftime("%-m/%-d/%Y %H:%M")

        call_logs = await client.get_call_logs(
            start_date=start, end_date=end, page_size=100,
        )

        found_ids = [str(c.get("CallID", "?")) for c in call_logs]
        logger.info(f"1Stream: Looking for CallID={call_id_str} in {found_ids}")

        for call in call_logs:
            if str(call.get("CallID", "")).strip() == call_id_str:
                return call

        if window_minutes < 60:
            logger.info(
                f"1Stream: CallID {call_id_str} not found in ±{window_minutes}min, "
                f"widening search"
            )

    return None


async def _find_onestream_call_by_metadata(
    client,
    webhook_body: dict,
) -> dict | None:
    """Find a call log entry by extension + phone + timestamp (CallEnd).

    The CallEnd webhook's CallID is an in-flight ID that doesn't match
    GetCallLogs. Instead we match by extension number, phone number, and
    closest timestamp.
    """
    from datetime import timedelta

    dt = _parse_onestream_timestamp(webhook_body.get("DateTimeStamp"))
    ext = webhook_body.get("ExtensionNumber", "").strip()
    phone = _extract_phone_from_webhook(webhook_body)

    logger.info(f"1Stream: CallEnd lookup — ext={ext}, phone={phone}, time={dt}")

    if not phone:
        logger.warning("1Stream: Could not extract phone number from CallEnd webhook")
        return None

    # Search a window around the call end time
    # CallEnd fires at call end; the call log's StartDate could be much earlier
    for window_minutes in (15, 30, 60):
        start = (dt - timedelta(minutes=window_minutes)).strftime("%-m/%-d/%Y %H:%M")
        end = (dt + timedelta(minutes=5)).strftime("%-m/%-d/%Y %H:%M")

        call_logs = await client.get_call_logs(
            start_date=start, end_date=end, page_size=100,
        )

        # Log call details for debugging
        for i, call in enumerate(call_logs):
            logger.info(
                f"1Stream: Call[{i}] CallID={call.get('CallID')} "
                f"Ext={call.get('ExtensionNumber')!r} "
                f"Inbound={call.get('Inbound')} "
                f"OriginatedBy={call.get('OriginatedBy')!r} "
                f"Destination={call.get('Destination')!r} "
                f"DestName={call.get('DestinationName')!r}"
            )

        logger.info(
            f"1Stream: CallEnd search ±{window_minutes}min found "
            f"{len(call_logs)} calls, looking for phone={phone}"
        )

        # Match by phone number using the correct 1Stream fields:
        # - Inbound:  OriginatedBy = external phone, Destination = internal
        # - Outbound: OriginatedBy = internal ext,   Destination = external phone
        import re
        candidates = []
        for call in call_logs:
            originated = re.sub(r"[^\d]", "", str(call.get("OriginatedBy") or ""))
            destination = re.sub(r"[^\d]", "", str(call.get("Destination") or ""))
            call_ext = str(call.get("ExtensionNumber", "")).strip()

            # Check if the external phone matches either field
            phone_match = False
            if phone:
                for field_digits in (originated, destination):
                    if not field_digits or len(field_digits) < 7:
                        continue  # Skip short values (extensions, not phone numbers)
                    if phone in field_digits or field_digits in phone:
                        phone_match = True
                        break

            if phone_match:
                ext_match = (call_ext == ext) if ext else True
                candidates.append((call, ext_match))

        if candidates:
            ext_matches = [c for c, m in candidates if m]
            if ext_matches:
                logger.info(
                    f"1Stream: Matched {len(ext_matches)} call(s) by "
                    f"phone={phone} + ext={ext}"
                )
                return ext_matches[-1]
            logger.info(
                f"1Stream: Matched {len(candidates)} call(s) by "
                f"phone={phone} (ext mismatch)"
            )
            return candidates[-1][0]

        if window_minutes < 60:
            logger.info(
                f"1Stream: No phone match in ±{window_minutes}min, widening"
            )

    return None


async def _resolve_ticket_by_phone(
    halo_client: HaloClient,
    call_log: dict,
) -> int | None:
    """Resolve a Halo ticket by searching for the caller's phone number."""
    is_inbound = call_log.get("Inbound", True)

    # For inbound calls, search by caller's number (OriginatedBy)
    # For outbound calls, search by the dialled number (Destination)
    phone = (
        call_log.get("OriginatedBy") if is_inbound
        else call_log.get("Destination")
    )

    if not phone:
        return None

    # Strip common prefixes for search
    search_phone = phone.lstrip("+").lstrip("1") if len(phone) > 10 else phone

    try:
        results = await halo_client.search_tickets(
            query=search_phone,
            count=5,
        )

        if not results:
            return None

        # Return the first (most relevant) match
        for ticket in results:
            tid = ticket.get("id")
            if tid:
                return int(tid)

    except Exception:
        logger.debug(
            f"1Stream: Phone search failed for {search_phone}", exc_info=True,
        )

    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)
