"""
Mesh Email Security API Client

Provides methods to interact with the Mesh Email Security REST API
for searching email logs, viewing email event traces, and looking up customers.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MeshClient:
    """Client for Mesh Email Security REST API."""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize the Mesh Email Security client.

        Args:
            base_url: Mesh API URL (e.g., https://hub-us.emailsecurity.app)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http_client: Optional[httpx.AsyncClient] = None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Make an authenticated request to Mesh API.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "api/emaillogs/")
            params: Query parameters

        Returns:
            Response JSON
        """
        client = await self.get_http_client()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = await client.request(
            method=method,
            url=url,
            params=params,
            headers={
                "API-KEY": self.api_key,
                "Accept": "application/json",
            },
        )

        if response.status_code >= 400:
            body = response.text
            logger.error(
                f"Mesh API error: {response.status_code} {method} "
                f"{endpoint} - {body[:500]}"
            )

        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # Email Log endpoints
    # ──────────────────────────────────────────────

    async def search_email_logs(
        self,
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
            start: Start datetime in ISO format (YYYY-MM-DDTHH:mm:ss)
            end: End datetime in ISO format (YYYY-MM-DDTHH:mm:ss)
            sender_ip: Sender IP address filter
            message_id: Specific message ID
            size: Number of results to return (default 50)

        Returns:
            Email log results
        """
        endpoint = (
            "api/emaillogs-outbound/"
            if direction == "outbound"
            else "api/emaillogs/"
        )

        # Default to last 24 hours if no date range provided
        if not start or not end:
            now = datetime.now(timezone.utc)
            if not end:
                end = now.strftime("%Y-%m-%dT%H:%M:%S")
            if not start:
                start = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

        params: Dict[str, Any] = {
            "_from": 0, "_size": size,
            "start": start, "end": end,
        }

        if from_addr:
            params["from"] = from_addr
        if to_addr:
            params["to"] = to_addr
        if subject:
            params["subject"] = subject
        if status:
            params["status"] = status
        if verdict:
            params["verdict"] = verdict
        if sender_ip:
            params["sender_ip"] = sender_ip
        if message_id:
            params["message_id"] = message_id

        logger.info(
            f"Searching Mesh {direction} email logs: "
            f"from={from_addr}, to={to_addr}, subject={subject}, "
            f"status={status}, start={start}, end={end}"
        )
        return await self._request("GET", endpoint, params=params)

    async def get_email_log_events(self, queue_id: int) -> Any:
        """
        Get detailed event trace for a specific email by queue ID.

        Args:
            queue_id: The queue ID of the email

        Returns:
            Event trace details
        """
        logger.info(f"Fetching Mesh email events for queue_id={queue_id}")
        return await self._request(
            "GET", "api/emaillogs/events",
            params={"queue_id": queue_id},
        )

    async def get_email_by_message_id(
        self,
        message_id: str,
        direction: str = "inbound",
    ) -> Dict[str, Any]:
        """
        Look up an email by its message UUID and return its details + event trace.

        Searches email logs by message_id, then fetches the event trace for the
        matching email. Returns both the email metadata and events in one call.

        Args:
            message_id: The message UUID (e.g. "4b60e4ca-0a81-4464-a996-5b45e49f0bc6")
            direction: "inbound" or "outbound" (default "inbound")

        Returns:
            Dict with "email" (log entry) and "events" (event trace) keys,
            or an error dict if not found.
        """
        logger.info(f"Looking up Mesh email by message_id={message_id}")

        # Search for the email by message_id (extend time range to 30 days)
        now = datetime.now(timezone.utc)
        results = await self.search_email_logs(
            direction=direction,
            message_id=message_id,
            start=(now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
            end=now.strftime("%Y-%m-%dT%H:%M:%S"),
            size=1,
        )

        # Extract the email record from results
        emails = []
        if isinstance(results, dict):
            emails = results.get("data", results.get("results", []))
        elif isinstance(results, list):
            emails = results

        if not emails:
            logger.info(f"No email found for message_id={message_id}")
            return {"error": f"No email found with message_id {message_id}"}

        email = emails[0]
        queue_id = email.get("queue_id") or email.get("id")

        if not queue_id:
            logger.warning(f"Email found but no queue_id in response for {message_id}")
            return {"email": email, "events": None}

        # Fetch event trace
        try:
            events = await self.get_email_log_events(int(queue_id))
        except Exception as e:
            logger.warning(f"Failed to fetch events for queue_id={queue_id}: {e}")
            return {"email": email, "events": None, "events_error": str(e)}

        return {"email": email, "events": events}

    # ──────────────────────────────────────────────
    # Customer endpoints
    # ──────────────────────────────────────────────

    async def search_customers(
        self,
        filter_term: Optional[str] = None,
        size: int = 50,
    ) -> Any:
        """
        Search Mesh customers by domain or company name.

        Args:
            filter_term: Search term (company name or domain)
            size: Number of results to return (default 50)

        Returns:
            Paginated customer list
        """
        params: Dict[str, Any] = {"_from": 0, "_size": size}
        if filter_term:
            params["filter"] = filter_term

        logger.info(f"Searching Mesh customers: filter={filter_term}")
        return await self._request("GET", "api/customers/", params=params)
