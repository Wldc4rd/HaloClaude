"""
MCP Tool registrations for Mesh Email Security.

Registers Mesh tools on the existing HaloClaude MCP server
so they are available to Claude Desktop and other MCP clients.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp_server.server import mcp
from .client import MeshClient

logger = logging.getLogger(__name__)

# MeshClient instance, set during app startup
_mesh_client: Optional[MeshClient] = None


def set_mesh_client(client: MeshClient) -> None:
    """Set the Mesh client instance for tools to use."""
    global _mesh_client
    _mesh_client = client


def get_mesh_client() -> MeshClient:
    """Get the Mesh client, raising if not initialized."""
    if _mesh_client is None:
        raise RuntimeError("MeshClient not initialized. Is MESH_ENABLED=true?")
    return _mesh_client


# =============================================================================
# Mesh Email Security Tools
# =============================================================================

@mcp.tool(
    description="Search email logs in Mesh Email Security (Live Email Tracker). "
    "Supports filtering by sender, recipient, subject, status, verdict, "
    "date range, sender IP, and message ID."
)
async def mesh_search_email_logs(
    direction: str = "inbound",
    from_addr: Optional[str] = None,
    to_addr: Optional[str] = None,
    subject: Optional[str] = None,
    status: Optional[str] = None,
    verdict: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    sender_ip: Optional[str] = None,
    message_id: Optional[str] = None,
    size: int = 50,
) -> Any:
    """
    Search email logs from the Live Email Tracker.

    Args:
        direction: "inbound" or "outbound"
        from_addr: Sender email address filter
        to_addr: Recipient email address filter
        subject: Subject line filter
        status: Comma-separated statuses (quarantine, bounce, defer, delete, banner)
        verdict: Verdict filter (spam, clean, malware, etc.)
        start: Start datetime (YYYY-MM-DDTHH:mm:ss)
        end: End datetime (YYYY-MM-DDTHH:mm:ss)
        sender_ip: Sender IP address filter
        message_id: Specific message ID
        size: Number of results (default 50)
    """
    logger.info(
        f"MCP: mesh_search_email_logs called: direction={direction}, "
        f"from={from_addr}, to={to_addr}"
    )
    client = get_mesh_client()
    return await client.search_email_logs(
        direction=direction,
        from_addr=from_addr,
        to_addr=to_addr,
        subject=subject,
        status=status,
        verdict=verdict,
        start=start,
        end=end,
        sender_ip=sender_ip,
        message_id=message_id,
        size=size,
    )


@mcp.tool(
    description="Get the detailed event trace for a specific email from Mesh Email Security. "
    "Shows the full processing history including filtering decisions and delivery attempts."
)
async def mesh_get_email_events(queue_id: int) -> Any:
    """
    Get event trace for a specific email.

    Args:
        queue_id: The queue ID of the email
    """
    logger.info(f"MCP: mesh_get_email_events called with queue_id={queue_id}")
    client = get_mesh_client()
    return await client.get_email_log_events(queue_id)


@mcp.tool(
    description="Look up a specific email in Mesh Email Security by its message UUID/ID. "
    "Returns both the email metadata and full event trace in one call. "
    "Use this when you have a message ID from a quarantine alert or email notification."
)
async def mesh_get_email_by_id(
    message_id: str,
    direction: str = "inbound",
) -> Any:
    """
    Look up an email by its message UUID and return details + events.

    Args:
        message_id: The message UUID/ID to look up
        direction: "inbound" or "outbound" (default "inbound")
    """
    logger.info(f"MCP: mesh_get_email_by_id called with message_id={message_id}")
    client = get_mesh_client()
    return await client.get_email_by_message_id(
        message_id=message_id,
        direction=direction,
    )


@mcp.tool(
    description="Search Mesh Email Security customers by company name or email domain."
)
async def mesh_search_customers(filter_term: str) -> Any:
    """
    Search Mesh customers by company name or domain.

    Args:
        filter_term: Search term (company name or domain)
    """
    logger.info(f"MCP: mesh_search_customers called with filter_term={filter_term}")
    client = get_mesh_client()
    return await client.search_customers(filter_term=filter_term)
