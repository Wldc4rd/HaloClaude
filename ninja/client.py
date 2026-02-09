"""
NinjaRMM / NinjaOne API Client

Provides methods to interact with NinjaRMM's REST API v2 for fetching
device information, volumes, alerts, patches, software, and more.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from .auth import NinjaAuthManager

logger = logging.getLogger(__name__)


class NinjaClient:
    """Client for NinjaRMM REST API v2."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "monitoring",
    ):
        """
        Initialize the NinjaRMM client.

        Args:
            base_url: NinjaRMM instance URL (e.g., https://app.ninjarmm.com)
            client_id: OAuth client ID
            client_secret: OAuth client secret
            scope: OAuth scope (default: monitoring)
        """
        self.base_url = base_url.rstrip("/")

        self._auth = NinjaAuthManager(base_url, client_id, client_secret, scope)
        self._http_client: Optional[httpx.AsyncClient] = None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self):
        """Close HTTP client and auth manager."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        await self._auth.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Make an authenticated request to NinjaRMM API.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "v2/device/123")
            params: Query parameters

        Returns:
            Response JSON
        """
        token = await self._auth.get_token()
        client = await self.get_http_client()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = await client.request(
            method=method,
            url=url,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # Device endpoints (auto-injected during context injection)
    # ──────────────────────────────────────────────

    async def get_device(self, device_id: int) -> Dict[str, Any]:
        """
        Get device details by NinjaRMM device ID.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            Device details
        """
        logger.debug(f"Fetching NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}")

    async def get_device_volumes(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get disk volumes for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of volume details (capacity, free space, etc.)
        """
        logger.debug(f"Fetching volumes for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/volumes")

    async def get_device_alerts(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get active alerts for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of active alerts
        """
        logger.debug(f"Fetching alerts for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/alerts")

    async def get_device_os_patches(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get pending OS patches for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of OS patches
        """
        logger.debug(f"Fetching OS patches for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/os-patches")

    # ──────────────────────────────────────────────
    # On-demand endpoints (MCP tools + proxy agent tools)
    # ──────────────────────────────────────────────

    async def get_device_software(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get installed software for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of installed software
        """
        logger.debug(f"Fetching software for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/software")

    async def get_device_processors(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get CPU/processor information for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of processor details
        """
        logger.debug(f"Fetching processors for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/processors")

    async def get_device_last_user(self, device_id: int) -> Dict[str, Any]:
        """
        Get last logged-on user for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            Last logged-on user details
        """
        logger.debug(f"Fetching last user for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/last-logged-on-user")

    async def get_device_disk_drives(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get physical disk drive information for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of physical disk drives
        """
        logger.debug(f"Fetching disk drives for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/disks")

    async def get_device_network_interfaces(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get network interface information for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of network interfaces
        """
        logger.debug(f"Fetching network interfaces for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/network-interfaces")

    async def get_device_windows_services(self, device_id: int) -> List[Dict[str, Any]]:
        """
        Get Windows services for a device.

        Args:
            device_id: NinjaRMM device ID

        Returns:
            List of Windows services
        """
        logger.debug(f"Fetching Windows services for NinjaRMM device {device_id}")
        return await self._request("GET", f"v2/device/{device_id}/windows-services")

    async def search_devices(
        self,
        query: str,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Search for devices by name, logged-on user, IP address, etc.

        Args:
            query: Search query (hostname, username, IP, etc.)
            limit: Maximum number of results to return (default 25)

        Returns:
            List of matching device summaries
        """
        logger.debug(f"Searching NinjaRMM devices: {query}")
        result = await self._request("GET", "v2/devices/search", params={
            "q": query,
            "limit": limit,
        })
        devices = result if isinstance(result, list) else result.get("devices", [])
        logger.info(f"NinjaRMM device search returned {len(devices)} results")
        return devices
