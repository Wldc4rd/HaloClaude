"""
MCP Server for Halo PSA Tools

Exposes Halo PSA tools via the Model Context Protocol for use
by Claude Desktop and other MCP clients.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings

from config import get_settings
from halo.client import HaloClient

logger = logging.getLogger(__name__)

# Build auth configuration if Entra ID is configured
_settings = get_settings()
_auth_settings = None
_token_verifier = None

if _settings.entra_tenant_id and _settings.entra_client_id:
    from mcp.server.auth.settings import AuthSettings
    from mcp_server.auth import EntraTokenVerifier

    _auth_settings = AuthSettings(
        issuer_url=f"https://login.microsoftonline.com/{_settings.entra_tenant_id}/v2.0",
        resource_server_url=f"{_settings.public_base_url}/mcp",
    )
    _token_verifier = EntraTokenVerifier(
        tenant_id=_settings.entra_tenant_id,
        client_id=_settings.entra_client_id,
        static_key=_settings.litellm_master_key,
    )
    logger.info("MCP OAuth: Entra ID authentication enabled")

# Create the FastMCP server instance
# stateless_http=True enables remote HTTP connections
# Disable DNS rebinding protection to allow connections via reverse proxy
mcp = FastMCP(
    name="HaloClaude",
    stateless_http=True,
    streamable_http_path="/",
    auth=_auth_settings,
    token_verifier=_token_verifier,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

# HaloClient instance, set during app startup
_halo_client: Optional[HaloClient] = None


def set_halo_client(client: HaloClient) -> None:
    """Set the Halo client instance for tools to use."""
    global _halo_client
    _halo_client = client


def get_halo_client() -> HaloClient:
    """Get the Halo client, raising if not initialized."""
    if _halo_client is None:
        raise RuntimeError("HaloClient not initialized")
    return _halo_client


# =============================================================================
# Ticket Tools
# =============================================================================

@mcp.tool(
    description="Get detailed information about a specific ticket including "
    "status, priority, description, and all associated data."
)
async def get_ticket(ticket_id: int) -> Dict[str, Any]:
    """
    Retrieve ticket details from Halo PSA.

    Args:
        ticket_id: The ticket ID number
    """
    logger.info(f"MCP: get_ticket called with ticket_id={ticket_id}")
    client = get_halo_client()
    return await client.get_ticket(ticket_id)


@mcp.tool(
    description="Get the full history of actions and notes for a ticket. "
    "Use this to understand the timeline and communications on a ticket."
)
async def get_ticket_actions(ticket_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve ticket actions/notes from Halo PSA.

    Args:
        ticket_id: The ticket ID number
    """
    logger.info(f"MCP: get_ticket_actions called with ticket_id={ticket_id}")
    client = get_halo_client()
    return await client.get_ticket_actions(ticket_id)


@mcp.tool(
    description="Create a new ticket in Halo PSA. Requires a summary and client_id. "
    "Optionally provide details, user, priority, type, and categories."
)
async def create_ticket(
    summary: str,
    client_id: int,
    details: Optional[str] = None,
    user_id: Optional[int] = None,
    priority_id: Optional[int] = None,
    ticket_type_id: Optional[int] = None,
    category_1: Optional[str] = None,
    category_2: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new ticket in Halo PSA.

    Args:
        summary: Ticket summary/subject line
        client_id: Client/company ID
        details: Ticket description/details (supports HTML)
        user_id: Reporting user ID
        priority_id: Priority level ID
        ticket_type_id: Ticket type ID
        category_1: Primary category
        category_2: Secondary category
    """
    logger.info(f"MCP: create_ticket called with summary={summary}")
    client = get_halo_client()
    return await client.create_ticket(
        summary, client_id, details, user_id,
        priority_id, ticket_type_id, category_1, category_2,
    )


@mcp.tool(
    description="Update fields on an existing ticket. Provide ticket_id and any "
    "fields to change. Only provided fields will be updated."
)
async def update_ticket(
    ticket_id: int,
    summary: Optional[str] = None,
    details: Optional[str] = None,
    priority_id: Optional[int] = None,
    ticket_type_id: Optional[int] = None,
    category_1: Optional[str] = None,
    category_2: Optional[str] = None,
    agent_id: Optional[int] = None,
    team_id: Optional[int] = None,
    status_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Update an existing ticket in Halo PSA.

    Args:
        ticket_id: The ticket ID to update
        summary: New summary/subject line
        details: New description/details (supports HTML)
        priority_id: New priority level ID
        ticket_type_id: New ticket type ID
        category_1: New primary category
        category_2: New secondary category
        agent_id: New assigned agent ID
        team_id: New assigned team ID
        status_id: New status ID
    """
    logger.info(f"MCP: update_ticket called on ticket_id={ticket_id}")
    client = get_halo_client()
    return await client.update_ticket(
        ticket_id, summary, details, priority_id,
        ticket_type_id, category_1, category_2,
        agent_id, team_id, status_id,
    )


@mcp.tool(
    description="Set the priority on a ticket. Priority IDs: "
    "1=Critical, 2=High, 3=Medium, 4=Low. "
    "Optionally set the SLA if it is incorrect."
)
async def set_ticket_priority(
    ticket_id: int,
    priority_id: int,
    sla_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Set priority (and optionally SLA) on a Halo PSA ticket.

    Args:
        ticket_id: The ticket ID to update
        priority_id: Priority level (1=Critical, 2=High, 3=Medium, 4=Low)
        sla_id: SLA ID override (1=Default, 3=Bronze/Break-Fix,
                4=Managed Gold, 5=Managed Silver)
    """
    logger.info(
        f"MCP: set_ticket_priority called on ticket_id={ticket_id}, "
        f"priority_id={priority_id}, sla_id={sla_id}"
    )
    client = get_halo_client()
    return await client.update_ticket(
        ticket_id=ticket_id,
        priority_id=priority_id,
        sla_id=sla_id,
    )


@mcp.tool(
    description="Close/resolve a ticket. Optionally include a private closure note "
    "summarizing the resolution."
)
async def close_ticket(
    ticket_id: int,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Close/resolve a ticket in Halo PSA.

    Args:
        ticket_id: The ticket ID to close
        note: Optional closure/resolution note (private by default)
    """
    logger.info(f"MCP: close_ticket called on ticket_id={ticket_id}")
    client = get_halo_client()
    return await client.close_ticket(ticket_id, note)


@mcp.tool(
    description="Create or update a note on a ticket. "
    "To create a new note, provide ticket_id and note. "
    "To update an existing note, also provide action_id. "
    "Defaults to a private/agent-only note. "
    "Set hiddenfromuser to false to make the note visible to the end user."
)
async def create_ticket_note(
    ticket_id: int,
    note: str,
    hiddenfromuser: bool = True,
    action_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create or update a note/action on a Halo PSA ticket.

    Args:
        ticket_id: The ticket ID to add the note to
        note: The note content (supports HTML)
        hiddenfromuser: If true, note is private/agent-only (default true)
        action_id: The action ID to update. Omit to create a new note.
    """
    logger.info(f"MCP: create_ticket_note called on ticket_id={ticket_id}, action_id={action_id}")
    client = get_halo_client()
    return await client.create_ticket_note(ticket_id, note, hiddenfromuser, action_id)


@mcp.tool(
    description="Search for tickets matching a query. Use this to find "
    "related tickets, similar issues, or past resolutions."
)
async def search_tickets(
    query: str,
    count: int = 10,
    client_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Search tickets in Halo PSA.

    Args:
        query: Search query (e.g., error message, topic, keyword)
        count: Maximum number of results (default 10)
        client_id: Filter results to a specific client/company
        user_id: Filter results to a specific user
    """
    logger.info(f"MCP: search_tickets called with query={query}")
    client = get_halo_client()
    return await client.search_tickets(query, count, client_id, user_id)


# =============================================================================
# User Tools
# =============================================================================

@mcp.tool(
    description="Get information about a user including their contact details, "
    "company affiliation, and role."
)
async def get_user(user_id: int) -> Dict[str, Any]:
    """
    Retrieve user details from Halo PSA.

    Args:
        user_id: The user ID number
    """
    logger.info(f"MCP: get_user called with user_id={user_id}")
    client = get_halo_client()
    return await client.get_user(user_id)


@mcp.tool(
    description="Get a list of tickets for a specific user. Use this to see "
    "if the user has related issues or patterns."
)
async def get_user_tickets(
    user_id: int,
    count: int = 10,
    open_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Retrieve tickets for a user from Halo PSA.

    Args:
        user_id: The user ID number
        count: Maximum number of tickets to return (default 10)
        open_only: Only return open/active tickets (default False)
    """
    logger.info(f"MCP: get_user_tickets called with user_id={user_id}")
    client = get_halo_client()
    return await client.get_user_tickets(user_id, count, open_only)


# =============================================================================
# Client/Company Tools
# =============================================================================

@mcp.tool(
    description="Get information about a client/company including their "
    "details, service level, and configuration."
)
async def get_client(client_id: int) -> Dict[str, Any]:
    """
    Retrieve client/company details from Halo PSA.

    Args:
        client_id: The client/company ID number
    """
    logger.info(f"MCP: get_client called with client_id={client_id}")
    client = get_halo_client()
    return await client.get_client(client_id)


@mcp.tool(
    description="Get a list of recent tickets for a client/company. Use this "
    "to see company-wide issues or patterns."
)
async def get_client_tickets(
    client_id: int,
    count: int = 10,
    open_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Retrieve tickets for a client from Halo PSA.

    Args:
        client_id: The client/company ID number
        count: Maximum number of tickets to return (default 10)
        open_only: Only return open/active tickets (default False)
    """
    logger.info(f"MCP: get_client_tickets called with client_id={client_id}")
    client = get_halo_client()
    return await client.get_client_tickets(client_id, count, open_only)


@mcp.tool(
    description="List tickets with structured filters. Unlike search_tickets (keyword search), "
    "this filters by client, open/closed status, date ranges, assigned agent, or linked asset. "
    "Returns summary-level data including status, priority, agent, and last action date."
)
async def list_tickets(
    client_id: Optional[int] = None,
    open_only: bool = False,
    closed_only: bool = False,
    agent_id: Optional[int] = None,
    asset_id: Optional[int] = None,
    opened_after: Optional[str] = None,
    opened_before: Optional[str] = None,
    last_updated_after: Optional[str] = None,
    last_updated_before: Optional[str] = None,
    count: int = 25,
) -> List[Dict[str, Any]]:
    """
    List tickets with structured filters.

    Args:
        client_id: Filter by client/company ID
        open_only: Only return open/active tickets
        closed_only: Only return closed tickets
        agent_id: Filter by assigned agent ID
        asset_id: Filter by linked asset ID
        opened_after: Only tickets opened after this date (ISO format)
        opened_before: Only tickets opened before this date (ISO format)
        last_updated_after: Only tickets last updated after this date (ISO format)
        last_updated_before: Only tickets last updated before this date (ISO format)
        count: Maximum results (default 25, max 100)
    """
    logger.info("MCP: list_tickets called")
    client = get_halo_client()
    kwargs: Dict[str, Any] = {
        "client_id": client_id,
        "open_only": open_only,
        "closed_only": closed_only,
        "agent_id": agent_id,
        "asset_id": asset_id,
        "count": count,
        "order": "dateoccured",
        "orderdesc": True,
    }
    if opened_after or opened_before:
        kwargs["datesearch"] = "dateoccured"
        kwargs["startdate"] = opened_after
        kwargs["enddate"] = opened_before
    kwargs["lastupdatefromdate"] = last_updated_after
    kwargs["lastupdatetodate"] = last_updated_before
    return await client.list_tickets(**kwargs)


@mcp.tool(
    description="Close multiple tickets at once with a shared closure note. "
    "Returns a summary showing which succeeded and which failed."
)
async def batch_close_tickets(
    ticket_ids: List[int],
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Close multiple tickets at once.

    Args:
        ticket_ids: Array of ticket IDs to close
        note: Closure note applied to all tickets (private)
    """
    logger.info(f"MCP: batch_close_tickets called for {len(ticket_ids)} tickets")
    client = get_halo_client()
    return await client.batch_close_tickets(ticket_ids, note)


@mcp.tool(
    description="Get tickets that are linked/related to a specific ticket. "
    "Shows associated issues and parent/child relationships."
)
async def get_related_tickets(ticket_id: int) -> List[Dict[str, Any]]:
    """
    Get related/linked tickets from Halo PSA.

    Args:
        ticket_id: The ticket ID to find related tickets for
    """
    logger.info(f"MCP: get_related_tickets called with ticket_id={ticket_id}")
    client = get_halo_client()
    return await client.get_related_tickets(ticket_id)


# =============================================================================
# User Tools (additions)
# =============================================================================

@mcp.tool(
    description="List users belonging to a client/company. Returns active users by default. "
    "Set include_inactive to true to also see departed/disabled employees."
)
async def get_client_users(
    client_id: int,
    include_active: bool = True,
    include_inactive: bool = False,
    search: Optional[str] = None,
    count: int = 50,
) -> List[Dict[str, Any]]:
    """
    List users for a client/company.

    Args:
        client_id: The client/company ID
        include_active: Include active users (default True)
        include_inactive: Include inactive/departed users (default False)
        search: Text search filter
        count: Maximum results (default 50)
    """
    logger.info(f"MCP: get_client_users called with client_id={client_id}")
    client = get_halo_client()
    return await client.get_client_users(
        client_id, include_active, include_inactive, search, count,
    )


# =============================================================================
# Contract / Billing Tools
# =============================================================================

@mcp.tool(
    description="Get recurring invoices for a contract or client. Returns the "
    "actual billed line items with descriptions, quantities, and prices. "
    "This is the definitive source of truth for what services a client is "
    "paying for on a contract."
)
async def get_recurring_invoices(
    contract_id: Optional[int] = None,
    client_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve recurring invoices from Halo PSA.

    Args:
        contract_id: Filter by contract ID
        client_id: Filter by client/company ID
    """
    logger.info(
        f"MCP: get_recurring_invoices called with "
        f"contract_id={contract_id}, client_id={client_id}"
    )
    client = get_halo_client()
    return await client.get_recurring_invoices(contract_id, client_id)


# =============================================================================
# Asset Tools
# =============================================================================

@mcp.tool(
    description="Search for assets/devices in Halo PSA by name or hostname. "
    "Optionally filter by client/company."
)
async def search_assets(
    search: Optional[str] = None,
    client_id: Optional[int] = None,
    count: int = 50,
) -> List[Dict[str, Any]]:
    """
    Search assets in Halo PSA.

    Args:
        search: Text search (asset name, hostname, etc.)
        client_id: Filter by client/company ID
        count: Maximum results (default 50)
    """
    logger.info(f"MCP: search_assets called with search={search}")
    client = get_halo_client()
    return await client.search_assets(
        client_id=client_id, search=search, count=count,
    )


@mcp.tool(
    description="Get information about an asset/device including its "
    "configuration, specifications, and history."
)
async def get_asset(asset_id: int) -> Dict[str, Any]:
    """
    Retrieve asset details from Halo PSA.

    Args:
        asset_id: The asset ID number
    """
    logger.info(f"MCP: get_asset called with asset_id={asset_id}")
    client = get_halo_client()
    return await client.get_asset(asset_id)


# =============================================================================
# Knowledge Base Tools
# =============================================================================

@mcp.tool(
    description="Search the knowledge base for articles matching a query. "
    "Use this to find documented solutions and procedures."
)
async def search_kb(
    query: str,
    count: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search knowledge base in Halo PSA.

    Args:
        query: Search query for knowledge base articles
        count: Maximum number of results (default 5)
    """
    logger.info(f"MCP: search_kb called with query={query}")
    client = get_halo_client()
    return await client.search_kb(query, count)


@mcp.tool(
    description="Get the full content of a specific knowledge base article."
)
async def get_kb_article(article_id: int) -> Dict[str, Any]:
    """
    Retrieve a knowledge base article from Halo PSA.

    Args:
        article_id: The knowledge base article ID
    """
    logger.info(f"MCP: get_kb_article called with article_id={article_id}")
    client = get_halo_client()
    return await client.get_kb_article(article_id)


# =============================================================================
# Attachment / Call Recording Tools
# =============================================================================

@mcp.tool(
    description="List attachments on a Halo ticket. Use this to find call "
    "recording MP3s before transcribing them."
)
async def list_ticket_attachments(ticket_id: int) -> List[Dict[str, Any]]:
    """
    List all attachments on a Halo ticket.

    Args:
        ticket_id: The ticket ID to list attachments for
    """
    logger.info(f"MCP: list_ticket_attachments called with ticket_id={ticket_id}")
    client = get_halo_client()
    return await client.get_ticket_attachments(ticket_id)


@mcp.tool(
    description="Transcribe and summarize a call recording. Accepts either a "
    "direct URL to an audio file or a Halo attachment_id. Downloads the audio, "
    "transcribes it with Whisper, then sends the transcript to Claude for "
    "structured analysis (summary, sentiment, next steps, coaching, transcript). "
    "If ticket_id is provided, posts the result as a private note on the ticket. "
    "For Halo attachments, use list_ticket_attachments first to find the attachment_id."
)
async def transcribe_call(
    url: Optional[str] = None,
    ticket_id: Optional[int] = None,
    attachment_id: Optional[int] = None,
    post_note: bool = True,
) -> str:
    """
    Transcribe and analyze a call recording.

    Args:
        url: Direct URL to an audio file (MP3, WAV, etc.). Use this for
             recordings not stored in Halo.
        ticket_id: Halo ticket ID. Required if posting a note or using attachment_id.
        attachment_id: Halo attachment ID. Use list_ticket_attachments to find this.
        post_note: If true and ticket_id is set, post transcription as a private note
                   (default true)
    """
    logger.info(
        f"MCP: transcribe_call called with ticket_id={ticket_id}, "
        f"attachment_id={attachment_id}, url={'<provided>' if url else None}"
    )
    from .transcribe import transcribe_call_recording

    client = get_halo_client()
    return await transcribe_call_recording(
        halo_client=client,
        ticket_id=ticket_id,
        attachment_id=attachment_id,
        url=url,
        post_note=post_note,
    )
