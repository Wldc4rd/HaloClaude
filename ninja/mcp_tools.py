"""
MCP Tool registrations for NinjaRMM / NinjaOne.

Registers NinjaRMM tools on the existing HaloClaude MCP server
so they are available to Claude Desktop and other MCP clients.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp_server.server import mcp
from .client import NinjaClient

logger = logging.getLogger(__name__)

# NinjaClient instance, set during app startup
_ninja_client: Optional[NinjaClient] = None


def set_ninja_client(client: NinjaClient) -> None:
    """Set the NinjaRMM client instance for tools to use."""
    global _ninja_client
    _ninja_client = client


def get_ninja_client() -> NinjaClient:
    """Get the NinjaRMM client, raising if not initialized."""
    if _ninja_client is None:
        raise RuntimeError("NinjaClient not initialized. Is NINJA_ENABLED=true?")
    return _ninja_client


# =============================================================================
# NinjaRMM Device Tools
# =============================================================================

@mcp.tool(
    description="Get device details from NinjaRMM including name, OS, "
    "online/offline status, IP addresses, model, and last contact time."
)
async def ninja_get_device(device_id: int) -> Dict[str, Any]:
    """
    Get device information from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device(device_id)


@mcp.tool(
    description="Get disk volume information for a device from NinjaRMM "
    "including drive letters, capacity, free space, and filesystem type."
)
async def ninja_get_device_volumes(device_id: int) -> List[Dict[str, Any]]:
    """
    Get disk volumes for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_volumes called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_volumes(device_id)


@mcp.tool(
    description="Get active alerts/triggered conditions for a device from NinjaRMM. "
    "Shows current problems and monitoring alerts."
)
async def ninja_get_device_alerts(device_id: int) -> List[Dict[str, Any]]:
    """
    Get alerts for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_alerts called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_alerts(device_id)


@mcp.tool(
    description="Get pending OS patches for a device from NinjaRMM. "
    "Shows which Windows/OS updates are waiting to be installed."
)
async def ninja_get_device_os_patches(device_id: int) -> List[Dict[str, Any]]:
    """
    Get pending OS patches for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_os_patches called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_os_patches(device_id)


@mcp.tool(
    description="Get installed software list for a device from NinjaRMM. "
    "Use this to check if specific software is installed or verify versions."
)
async def ninja_get_device_software(device_id: int) -> List[Dict[str, Any]]:
    """
    Get installed software for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_software called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_software(device_id)


@mcp.tool(
    description="Get CPU/processor details for a device from NinjaRMM "
    "including model, core count, and clock speed."
)
async def ninja_get_device_processors(device_id: int) -> List[Dict[str, Any]]:
    """
    Get processor information for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_processors called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_processors(device_id)


@mcp.tool(
    description="Get the last logged-on user for a device from NinjaRMM."
)
async def ninja_get_device_last_user(device_id: int) -> Dict[str, Any]:
    """
    Get last logged-on user for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_last_user called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_last_user(device_id)


@mcp.tool(
    description="Get physical disk drive details for a device from NinjaRMM "
    "including model, size, interface type, and media type (SSD/HDD)."
)
async def ninja_get_device_disk_drives(device_id: int) -> List[Dict[str, Any]]:
    """
    Get physical disk drives for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_disk_drives called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_disk_drives(device_id)


@mcp.tool(
    description="Get network interface details for a device from NinjaRMM "
    "including IP configuration, MAC addresses, and connection status."
)
async def ninja_get_device_network_interfaces(device_id: int) -> List[Dict[str, Any]]:
    """
    Get network interfaces for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_network_interfaces called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_network_interfaces(device_id)


@mcp.tool(
    description="Get Windows services list for a device from NinjaRMM "
    "including service name, status, and startup type."
)
async def ninja_get_device_windows_services(device_id: int) -> List[Dict[str, Any]]:
    """
    Get Windows services for a device from NinjaRMM.

    Args:
        device_id: The NinjaRMM device ID
    """
    logger.info(f"MCP: ninja_get_device_windows_services called with device_id={device_id}")
    client = get_ninja_client()
    return await client.get_device_windows_services(device_id)
