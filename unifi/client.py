"""UniFi Network API Client.

Provides a generic request method for querying the UniFi Site Manager
and Network APIs via api.ui.com.
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ui.com"


class UniFiClient:
    """Client for the UniFi Site Manager / Network API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._http_client: Optional[httpx.AsyncClient] = None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0, follow_redirects=True,
            )
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Any = None,
    ) -> Any:
        """Make an authenticated request to the UniFi API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g. /v1/hosts, /v1/sites/{id}/clients)
            params: Query parameters
            json: JSON body (for POST requests)

        Returns:
            Parsed JSON response
        """
        client = await self.get_http_client()
        url = f"{BASE_URL}/{path.lstrip('/')}"

        response = await client.request(
            method=method,
            url=url,
            params=params,
            json=json,
            headers={
                "X-API-KEY": self.api_key,
                "Accept": "application/json",
            },
        )

        if response.status_code >= 400:
            body = response.text
            logger.error(
                f"UniFi API error: {response.status_code} {method} "
                f"{path} - {body[:500]}"
            )

        response.raise_for_status()
        return response.json()
