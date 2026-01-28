"""
MCP Server for Halo PSA Tools

Exposes Halo PSA tools via the Model Context Protocol for use
by Claude Desktop and other MCP clients.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings

from halo.client import HaloClient

logger = logging.getLogger(__name__)

# Create the FastMCP server instance
# stateless_http=True enables remote HTTP connections
# Disable DNS rebinding protection to allow connections via reverse proxy
mcp = FastMCP(
    name="HaloClaude",
    stateless_http=True,
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


# =============================================================================
# Asset Tools
# =============================================================================

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
