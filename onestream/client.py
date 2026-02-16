"""
1Stream (BVOIP) API Client

Provides methods to query call logs and download call recordings
from the 1Stream REST API.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class OneStreamClient:
    """Client for 1Stream REST API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
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

    async def _request_json(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated JSON request to 1Stream API."""
        client = await self.get_http_client()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = await client.request(
            method=method,
            url=url,
            params=params,
            headers={
                "Authorization": self.api_key,
                "Accept": "application/json",
            },
        )

        if response.status_code >= 400:
            body = response.text
            logger.error(
                f"1Stream API error: {response.status_code} {method} "
                f"{endpoint} - {body[:500]}"
            )

        response.raise_for_status()
        return response.json()

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Convert any common date format to M/D/YYYY or M/D/YYYY HH:MM for the 1Stream API."""
        date_str = date_str.strip()
        # Already in M/D/YYYY format
        if "/" in date_str and not date_str.startswith("20"):
            return date_str

        # Try common formats and convert
        for fmt in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.hour or dt.minute:
                    return dt.strftime("%-m/%-d/%Y %H:%M")
                return dt.strftime("%-m/%-d/%Y")
            except ValueError:
                continue

        # Couldn't parse — pass through and let the API decide
        return date_str

    # ──────────────────────────────────────────────
    # Call Logs
    # ──────────────────────────────────────────────

    async def get_call_logs(
        self,
        start_date: str,
        end_date: str,
        ext: str = "",
        page_number: int = 1,
        page_size: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search call logs by date range.

        Args:
            start_date: Start date (any format: YYYY-MM-DD, M/D/YYYY, etc.)
            end_date: End date (same)
            ext: Extension filter (empty string for all)
            page_number: Page number (1-indexed)
            page_size: Results per page

        Returns:
            List of call log dicts
        """
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)
        logger.info(
            f"Fetching 1Stream call logs: {start_date} to {end_date}"
            f"{f' ext={ext}' if ext else ''}"
        )
        result = await self._request_json(
            "GET",
            "api/ClientAccess.svc/GetCallLogs",
            params={
                "ext": ext,
                "startDate": start_date,
                "endDate": end_date,
                "pageNumber": page_number,
                "pageSize": page_size,
            },
        )

        # Debug: log the raw response structure
        if isinstance(result, list):
            logger.info(f"1Stream returned list with {len(result)} items")
            return result
        if isinstance(result, dict):
            logger.info(
                f"1Stream returned dict with keys: {list(result.keys())[:10]}"
            )
            # Try common wrapper keys
            for key in ("LogDetails", "data", "results", "CallLogs", "callLogs", "Records", "records"):
                if key in result:
                    items = result[key]
                    if isinstance(items, list):
                        logger.info(f"1Stream: found {len(items)} items under '{key}'")
                        return items
                    if items is None:
                        logger.info(f"1Stream: '{key}' is null (no results)")
                        return []
            # If it's a single call record dict, wrap it
            if "CallID" in result:
                logger.info("1Stream: single call record returned")
                return [result]
            logger.warning(f"1Stream: unexpected dict structure, returning empty")
            return []
        logger.warning(f"1Stream: unexpected response type {type(result)}, returning empty")
        return []

    # ──────────────────────────────────────────────
    # Recordings
    # ──────────────────────────────────────────────

    async def download_recording(self, url: str) -> bytes:
        """
        Download a call recording MP3 from a DownloadRecording URL.

        Args:
            url: Full URL from the DownloadRecording field in call logs

        Returns:
            Raw MP3 bytes
        """
        logger.info(f"Downloading 1Stream recording: {url[:80]}...")
        client = await self.get_http_client()

        # Use longer timeout for potentially large files
        response = await client.get(
            url,
            headers={"Authorization": self.api_key},
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        response.raise_for_status()

        logger.info(f"Downloaded recording: {len(response.content)} bytes")
        return response.content
