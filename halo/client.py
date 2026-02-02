"""
Halo PSA API Client

Provides methods to interact with Halo's REST API for fetching
tickets, users, clients, assets, and knowledge base articles.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from .auth import HaloAuthManager

logger = logging.getLogger(__name__)


class HaloClient:
    """Client for Halo PSA REST API."""
    
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
    ):
        """
        Initialize the Halo client.
        
        Args:
            base_url: Halo instance URL (e.g., https://company.halopsa.com)
            client_id: OAuth client ID
            client_secret: OAuth client secret
        """
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api"
        
        self._auth = HaloAuthManager(base_url, client_id, client_secret)
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
        json: Optional[Any] = None,
    ) -> Any:
        """
        Make an authenticated request to Halo API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (without /api prefix)
            params: Query parameters
            json: JSON body
            
        Returns:
            Response JSON
        """
        token = await self._auth.get_token()
        client = await self.get_http_client()
        
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        response = await client.request(
            method=method,
            url=url,
            params=params,
            json=json,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()

        return response.json()

    async def _request_bytes(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Make an authenticated request and return raw bytes."""
        token = await self._auth.get_token()
        client = await self.get_http_client()

        url = f"{self.api_url}/{endpoint.lstrip('/')}"

        response = await client.request(
            method=method,
            url=url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()

        return response.content

    # =========================================================================
    # Ticket Operations
    # =========================================================================
    
    async def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Get ticket details by ID.
        
        Args:
            ticket_id: The ticket ID
            
        Returns:
            Ticket details
        """
        logger.debug(f"Fetching ticket {ticket_id}")
        return await self._request("GET", f"tickets/{ticket_id}")
    
    async def get_ticket_actions(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Get all actions/notes for a ticket.
        
        Args:
            ticket_id: The ticket ID
            
        Returns:
            List of ticket actions
        """
        logger.debug(f"Fetching actions for ticket {ticket_id}")
        result = await self._request("GET", "actions", params={
            "ticket_id": ticket_id,
        })
        # Halo returns {"actions": [...], "record_count": N}
        actions = result.get("actions", [])
        logger.info(f"Fetched {len(actions)} actions for ticket {ticket_id}")
        return actions
    
    async def create_ticket_note(
        self,
        ticket_id: int,
        note: str,
        hiddenfromuser: bool = True,
        action_id: Optional[int] = None,
    ) -> Any:
        """
        Create or update a note/action on a ticket.

        Args:
            ticket_id: The ticket ID
            note: Note content (supports HTML)
            hiddenfromuser: If True, note is private/agent-only
            action_id: If provided, updates an existing action instead of creating

        Returns:
            Created/updated action details
        """
        action = {
            "ticket_id": ticket_id,
            "note": note,
            "hiddenfromuser": hiddenfromuser,
            "outcome": "Note",
        }
        if action_id is not None:
            action["id"] = action_id
            logger.info(f"Updating note {action_id} on ticket {ticket_id}")
        else:
            logger.info(f"Creating note on ticket {ticket_id} (private={hiddenfromuser})")
        return await self._request("POST", "actions", json=[action])

    async def create_ticket(
        self,
        summary: str,
        client_id: int,
        details: Optional[str] = None,
        user_id: Optional[int] = None,
        priority_id: Optional[int] = None,
        ticket_type_id: Optional[int] = None,
        category_1: Optional[str] = None,
        category_2: Optional[str] = None,
    ) -> Any:
        """
        Create a new ticket.

        Args:
            summary: Ticket summary/subject
            client_id: Client/company ID
            details: Ticket description/details
            user_id: Reporting user ID
            priority_id: Priority level ID
            ticket_type_id: Ticket type ID
            category_1: Primary category
            category_2: Secondary category

        Returns:
            Created ticket details
        """
        logger.info(f"Creating ticket: {summary}")
        ticket: Dict[str, Any] = {
            "summary": summary,
            "client_id": client_id,
        }
        if details is not None:
            ticket["details"] = details
        if user_id is not None:
            ticket["user_id"] = user_id
        if priority_id is not None:
            ticket["priority_id"] = priority_id
        if ticket_type_id is not None:
            ticket["tickettype_id"] = ticket_type_id
        if category_1 is not None:
            ticket["category_1"] = category_1
        if category_2 is not None:
            ticket["category_2"] = category_2
        return await self._request("POST", "tickets", json=[ticket])

    async def update_ticket(
        self,
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
    ) -> Any:
        """
        Update an existing ticket.

        Args:
            ticket_id: The ticket ID to update
            summary: New summary/subject
            details: New description/details
            priority_id: New priority level ID
            ticket_type_id: New ticket type ID
            category_1: New primary category
            category_2: New secondary category
            agent_id: New assigned agent ID
            team_id: New assigned team ID
            status_id: New status ID

        Returns:
            Updated ticket details
        """
        logger.info(f"Updating ticket {ticket_id}")
        ticket: Dict[str, Any] = {"id": ticket_id}
        if summary is not None:
            ticket["summary"] = summary
        if details is not None:
            ticket["details"] = details
        if priority_id is not None:
            ticket["priority_id"] = priority_id
        if ticket_type_id is not None:
            ticket["tickettype_id"] = ticket_type_id
        if category_1 is not None:
            ticket["category_1"] = category_1
        if category_2 is not None:
            ticket["category_2"] = category_2
        if agent_id is not None:
            ticket["agent_id"] = agent_id
        if team_id is not None:
            ticket["team_id"] = team_id
        if status_id is not None:
            ticket["status_id"] = status_id
        return await self._request("POST", "tickets", json=[ticket])

    async def close_ticket(
        self,
        ticket_id: int,
        note: Optional[str] = None,
    ) -> Any:
        """
        Close/resolve a ticket with an optional closure note.

        Args:
            ticket_id: The ticket ID to close
            note: Optional closure note (private by default)

        Returns:
            Updated ticket details
        """
        logger.info(f"Closing ticket {ticket_id}")
        result = await self._request(
            "POST",
            "tickets",
            json=[{"id": ticket_id, "status_id": 9}],
        )
        if note:
            await self.create_ticket_note(
                ticket_id=ticket_id,
                note=note,
                hiddenfromuser=True,
            )
        return result

    async def search_tickets(
        self,
        query: str,
        count: int = 10,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for tickets.
        
        Args:
            query: Search query
            count: Maximum results to return
            client_id: Filter by client/company ID
            user_id: Filter by user ID
            
        Returns:
            List of matching tickets
        """
        logger.debug(f"Searching tickets: {query}")
        params = {
            "search": query,
            "count": count,
        }
        if client_id:
            params["client_id"] = client_id
        if user_id:
            params["user_id"] = user_id
            
        result = await self._request("GET", "tickets", params=params)
        return result.get("tickets", [])
    
    async def get_related_tickets(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Get tickets related/linked to a given ticket.

        Args:
            ticket_id: The ticket ID to find related tickets for

        Returns:
            List of related ticket summaries
        """
        logger.info(f"Fetching related tickets for ticket {ticket_id}")
        result = await self._request("GET", "tickets", params={
            "related_id": ticket_id,
            "count": 20,
        })
        tickets = result.get("tickets", [])
        logger.info(
            f"Related tickets for {ticket_id}: "
            f"{[t.get('id') for t in tickets]} "
            f"(record_count={result.get('record_count', '?')})"
        )
        return tickets

    # =========================================================================
    # User Operations
    # =========================================================================
    
    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """
        Get user details by ID.
        
        Args:
            user_id: The user ID
            
        Returns:
            User details
        """
        logger.debug(f"Fetching user {user_id}")
        return await self._request("GET", f"users/{user_id}")
    
    async def get_user_tickets(
        self,
        user_id: int,
        count: int = 10,
        open_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get tickets for a specific user.
        
        Args:
            user_id: The user ID
            count: Maximum results to return
            open_only: Only return open tickets
            
        Returns:
            List of user's tickets
        """
        logger.debug(f"Fetching tickets for user {user_id}")
        params = {
            "user_id": user_id,
            "count": count,
        }
        if open_only:
            params["open_only"] = "true"
            
        result = await self._request("GET", "tickets", params=params)
        return result.get("tickets", [])
    
    # =========================================================================
    # Client/Company Operations
    # =========================================================================
    
    async def get_client(self, client_id: int) -> Dict[str, Any]:
        """
        Get client/company details by ID.
        
        Args:
            client_id: The client ID
            
        Returns:
            Client details
        """
        logger.debug(f"Fetching client {client_id}")
        return await self._request("GET", f"client/{client_id}")
    
    async def get_client_tickets(
        self,
        client_id: int,
        count: int = 10,
        open_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get tickets for a specific client/company.
        
        Args:
            client_id: The client ID
            count: Maximum results to return
            open_only: Only return open tickets
            
        Returns:
            List of client's tickets
        """
        logger.debug(f"Fetching tickets for client {client_id}")
        params = {
            "client_id": client_id,
            "count": count,
        }
        if open_only:
            params["open_only"] = "true"
            
        result = await self._request("GET", "tickets", params=params)
        return result.get("tickets", [])
    
    async def get_client_contracts(
        self,
        client_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Get contracts for a specific client/company.

        Fetches the contract list, then fetches each contract individually
        to get full details (prepaid hour balances are only on the detail endpoint).

        Args:
            client_id: The client ID

        Returns:
            List of client's contracts with full details
        """
        logger.debug(f"Fetching contracts for client {client_id}")
        result = await self._request("GET", "ClientContract", params={
            "client_id": client_id,
        })
        contracts = result if isinstance(result, list) else result.get("contracts", result.get("items", []))
        if isinstance(contracts, dict):
            contracts = [contracts]
        logger.info(f"Fetched {len(contracts)} contracts for client {client_id}")

        # Fetch full details for each contract (list endpoint omits prepaid balances)
        if contracts:
            import asyncio
            detail_tasks = [
                self._request("GET", f"ClientContract/{c['id']}")
                for c in contracts if c.get("id")
            ]
            details = await asyncio.gather(*detail_tasks, return_exceptions=True)
            detailed = []
            for d in details:
                if isinstance(d, Exception):
                    logger.warning(f"Failed to fetch contract detail: {d}")
                elif isinstance(d, dict):
                    detailed.append(d)
            if detailed:
                contracts = detailed

        return contracts

    # =========================================================================
    # Attachment Operations
    # =========================================================================

    async def get_contract_attachments(
        self,
        contract_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Get document attachments for a contract.

        Args:
            contract_id: The contract ID

        Returns:
            List of attachment metadata dicts (id, filename, filesize, etc.)
        """
        logger.debug(f"Fetching attachments for contract {contract_id}")
        result = await self._request("GET", "Attachment", params={
            "type": 8,
            "unique_id": contract_id,
        })
        attachments = result.get("attachments", [])
        logger.info(f"Fetched {len(attachments)} attachments for contract {contract_id}")
        return attachments

    async def get_attachment_bytes(self, attachment_id: int) -> bytes:
        """
        Download an attachment as raw bytes.

        Args:
            attachment_id: The attachment ID

        Returns:
            Raw file bytes
        """
        logger.debug(f"Downloading attachment {attachment_id}")
        return await self._request_bytes("GET", f"Attachment/{attachment_id}")

    # =========================================================================
    # Asset Operations
    # =========================================================================

    async def get_asset(self, asset_id: int) -> Dict[str, Any]:
        """
        Get asset details by ID.
        
        Args:
            asset_id: The asset ID
            
        Returns:
            Asset details
        """
        logger.debug(f"Fetching asset {asset_id}")
        return await self._request("GET", f"asset/{asset_id}")
    
    # =========================================================================
    # Knowledge Base Operations
    # =========================================================================
    
    async def search_kb(
        self,
        query: str,
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge base.
        
        Args:
            query: Search query
            count: Maximum results to return
            
        Returns:
            List of matching KB articles
        """
        logger.debug(f"Searching KB: {query}")
        result = await self._request("GET", "KBArticle", params={
            "search": query,
            "count": count,
        })
        return result.get("articles", result) if isinstance(result, dict) else result
    
    async def get_kb_article(self, article_id: int) -> Dict[str, Any]:
        """
        Get a knowledge base article by ID.
        
        Args:
            article_id: The article ID
            
        Returns:
            Article details
        """
        logger.debug(f"Fetching KB article {article_id}")
        return await self._request("GET", f"KBArticle/{article_id}")
