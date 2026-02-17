"""MCP Tool registrations for UniFi Network API."""

import logging
from typing import Any, Optional

from mcp_server.server import mcp
from .client import UniFiClient

logger = logging.getLogger(__name__)

_unifi_client: Optional[UniFiClient] = None


def set_unifi_client(client: UniFiClient) -> None:
    """Set the UniFi client instance for tools to use."""
    global _unifi_client
    _unifi_client = client


def get_unifi_client() -> UniFiClient:
    """Get the UniFi client, raising if not initialized."""
    if _unifi_client is None:
        raise RuntimeError("UniFiClient not initialized. Is UNIFI_ENABLED=true?")
    return _unifi_client


@mcp.tool(
    description="""Query the UniFi Network API for network infrastructure data.

Available endpoints (all read-only):

Site Manager (global):
- GET /v1/hosts — List all UniFi hosts (UDMs, gateways, consoles)
- GET /v1/hosts/{id} — Get a specific host by ID
- GET /v1/sites — List all sites managed across all hosts
- GET /v1/devices — List all network devices (APs, switches, cameras)
- GET /v1/isp-metrics — Get ISP performance metrics
- GET /v1/sdwan-configs — List SD-WAN configurations
- GET /v1/sdwan-configs/{id} — Get a specific SD-WAN config
- GET /v1/sdwan-configs/{id}/status — Get SD-WAN config status

Network API (per-site — get siteId from /v1/sites first):
- GET /v1/sites/{siteId}/devices — List devices at a specific site
- GET /v1/sites/{siteId}/devices/{deviceId} — Get device details
- GET /v1/sites/{siteId}/devices/{deviceId}/statistics/latest — Latest device statistics
- GET /v1/sites/{siteId}/clients — List connected clients at a site
- GET /v1/sites/{siteId}/clients/{clientId} — Get connected client details
- GET /v1/sites/{siteId}/hotspot/vouchers — List hotspot vouchers
- GET /v1/info — Get application info

Pass the endpoint path and optional query parameters."""
)
async def unifi_api_request(
    path: str,
    params: Optional[dict] = None,
) -> Any:
    """Query a UniFi API endpoint.

    Args:
        path: API endpoint path (e.g. /v1/hosts, /v1/sites/{siteId}/clients)
        params: Optional query parameters (e.g. {"pageSize": 50})
    """
    if not path.startswith("/v1/"):
        return {"error": f"Invalid path: {path}. Must start with /v1/"}

    logger.info(f"MCP: unifi_api_request called: path={path}, params={params}")
    client = get_unifi_client()
    return await client.request("GET", path, params=params)
