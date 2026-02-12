"""
Halo PSA API Client

Provides methods to interact with Halo's REST API for fetching
tickets, users, clients, assets, and knowledge base articles.
"""

import asyncio
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

        max_retries = 5
        retry_waits = [15, 30, 45, 60, 60]  # seconds — long enough for rolling 5-min window
        auth_retried = False
        for attempt in range(max_retries + 1):
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
            if response.status_code == 401 and not auth_retried:
                # Token expired mid-pipeline — force refresh and retry once
                logger.warning(f"Halo API 401 ({method} {endpoint}), refreshing token")
                self._auth._token = None
                token = await self._auth.get_token()
                auth_retried = True
                continue
            if response.status_code == 429 and attempt < max_retries:
                wait = retry_waits[attempt]
                logger.warning(
                    f"Halo API rate limited ({method} {endpoint}), "
                    f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait)
                continue
            break

        if response.status_code >= 400:
            body = response.text
            logger.error(
                f"Halo API error: {response.status_code} {method} {endpoint} - {body[:500]}"
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
        asset_id: Optional[int] = None,
        sla_id: Optional[int] = None,
        user_id: Optional[int] = None,
        client_id: Optional[int] = None,
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
            sla_id: New SLA ID
            user_id: New reporting user ID
            client_id: New client/company ID

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
        if asset_id is not None:
            ticket["asset_id"] = asset_id
        if sla_id is not None:
            ticket["sla_id"] = sla_id
        if user_id is not None:
            ticket["user_id"] = user_id
        if client_id is not None:
            ticket["client_id"] = client_id
        return await self._request("POST", "tickets", json=[ticket])

    async def batch_close_tickets(
        self,
        ticket_ids: List[int],
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Close multiple tickets with a shared closure note.

        Args:
            ticket_ids: List of ticket IDs to close
            note: Optional closure note applied to all tickets (private)

        Returns:
            Summary dict with succeeded/failed ticket IDs
        """
        import asyncio
        logger.info(f"Batch closing {len(ticket_ids)} tickets")

        results: Dict[str, Any] = {"succeeded": [], "failed": []}

        async def _close_one(tid: int):
            try:
                await self.close_ticket(ticket_id=tid, note=note)
                results["succeeded"].append(tid)
            except Exception as e:
                logger.error(f"Failed to close ticket {tid}: {e}")
                results["failed"].append({"ticket_id": tid, "error": str(e)})

        await asyncio.gather(*[_close_one(tid) for tid in ticket_ids])
        logger.info(
            f"Batch close complete: {len(results['succeeded'])} succeeded, "
            f"{len(results['failed'])} failed"
        )
        return results

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
            json=[{"id": ticket_id, "status_id": 9, "_appointment01_ok": True}],
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

    async def list_tickets(
        self,
        client_id: Optional[int] = None,
        open_only: bool = False,
        closed_only: bool = False,
        agent_id: Optional[int] = None,
        asset_id: Optional[int] = None,
        datesearch: Optional[str] = None,
        startdate: Optional[str] = None,
        enddate: Optional[str] = None,
        lastupdatefromdate: Optional[str] = None,
        lastupdatetodate: Optional[str] = None,
        order: Optional[str] = None,
        orderdesc: bool = True,
        count: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        List tickets with rich filtering.

        Unlike search_tickets (keyword search), this uses structured filters
        for date ranges, agents, assets, and status.

        Args:
            client_id: Filter by client/company ID
            open_only: Only return open tickets
            closed_only: Only return closed tickets
            agent_id: Filter by assigned agent ID
            asset_id: Filter by linked asset ID
            datesearch: Date field to filter on (e.g. "dateoccured")
            startdate: Start date for datesearch filter (ISO format)
            enddate: End date for datesearch filter (ISO format)
            lastupdatefromdate: Only tickets updated on or after this date
            lastupdatetodate: Only tickets updated on or before this date
            order: Field name to order by
            orderdesc: Whether to order descending (default True)
            count: Maximum results to return (default 25, max 100)

        Returns:
            List of ticket summary objects
        """
        params: Dict[str, Any] = {
            "count": min(count, 100),
        }
        if client_id is not None:
            params["client_id"] = client_id
        if open_only:
            params["open_only"] = "true"
        if closed_only:
            params["closed_only"] = "true"
        if agent_id is not None:
            params["agent_id"] = agent_id
        if asset_id is not None:
            params["asset_id"] = asset_id
        if datesearch:
            params["datesearch"] = datesearch
        if startdate:
            params["startdate"] = startdate
        if enddate:
            params["enddate"] = enddate
        if lastupdatefromdate:
            params["lastupdatefromdate"] = lastupdatefromdate
        if lastupdatetodate:
            params["lastupdatetodate"] = lastupdatetodate
        if order:
            params["order"] = order
            params["orderdesc"] = str(orderdesc).lower()

        logger.debug(f"Listing tickets with filters: {params}")
        result = await self._request("GET", "tickets", params=params)
        tickets = result.get("tickets", [])
        logger.info(
            f"list_tickets returned {len(tickets)} tickets "
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
    
    async def get_client_users(
        self,
        client_id: int,
        include_active: bool = True,
        include_inactive: bool = False,
        search: Optional[str] = None,
        count: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List users belonging to a client/company.

        Args:
            client_id: The client/company ID
            include_active: Include active users (default True)
            include_inactive: Include inactive/departed users (default False)
            search: Optional text search filter
            count: Maximum results to return (default 50)

        Returns:
            List of user records for the client
        """
        params: Dict[str, Any] = {
            "client_id": client_id,
            "count": count,
            "includeactive": str(include_active).lower(),
            "includeinactive": str(include_inactive).lower(),
        }
        if search:
            params["search"] = search

        logger.debug(f"Fetching users for client {client_id}")
        result = await self._request("GET", "Users", params=params)
        users = result.get("users", []) if isinstance(result, dict) else result
        if isinstance(users, dict):
            users = [users]
        logger.info(f"Fetched {len(users)} users for client {client_id}")
        return users

    async def search_users(
        self,
        search: str,
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search all users across all clients by name or email.

        Args:
            search: Text search filter (name, email, etc.)
            count: Maximum results to return (default 10)

        Returns:
            List of matching user records
        """
        params: Dict[str, Any] = {
            "search": search,
            "count": count,
            "includeactive": "true",
        }

        logger.debug(f"Searching users: {search}")
        result = await self._request("GET", "Users", params=params)
        users = result.get("users", []) if isinstance(result, dict) else result
        if isinstance(users, dict):
            users = [users]
        logger.info(f"User search '{search}' returned {len(users)} results")
        return users

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
    # Opportunity Operations
    # =========================================================================

    async def create_opportunity(
        self,
        summary: str,
        client_id: int,
        details: Optional[str] = None,
        agent_id: Optional[int] = None,
    ) -> Any:
        """
        Create a new opportunity in Halo.

        Args:
            summary: Opportunity summary/subject
            client_id: Client/company ID
            details: Opportunity description
            agent_id: Assigned agent ID

        Returns:
            Created opportunity details
        """
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        logger.info(f"Creating opportunity: {summary}")
        opp: Dict[str, Any] = {
            "summary": summary,
            "client_id": client_id,
            "dateoccurred": now.isoformat(),
            "targetdate": (now + timedelta(days=30)).isoformat(),
        }
        if details is not None:
            opp["details"] = details
        if agent_id is not None:
            opp["agent_id"] = agent_id
        return await self._request("POST", "Opportunities", json=[opp])

    # =========================================================================
    # Recurring Invoice Operations
    # =========================================================================

    async def get_recurring_invoices(
        self,
        contract_id: Optional[int] = None,
        client_id: Optional[int] = None,
        include_lines: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get recurring invoices, optionally filtered by contract or client.

        Args:
            contract_id: Filter by contract ID
            client_id: Filter by client ID
            include_lines: Include line item details (default True)

        Returns:
            List of recurring invoice records with line items
        """
        params: Dict[str, Any] = {
            "includelines": str(include_lines).lower(),
        }
        if contract_id is not None:
            params["contract_id"] = contract_id
        if client_id is not None:
            params["client_id"] = client_id

        logger.debug(
            f"Fetching recurring invoices (contract_id={contract_id}, "
            f"client_id={client_id})"
        )
        result = await self._request("GET", "RecurringInvoice", params=params)
        invoices = result.get("invoices", []) if isinstance(result, dict) else result
        if isinstance(invoices, dict):
            invoices = [invoices]
        logger.info(f"Fetched {len(invoices)} recurring invoices")
        return invoices

    # =========================================================================
    # Contract Operations
    # =========================================================================

    async def update_contract(
        self,
        contract_id: int,
        note: Optional[str] = None,
    ) -> Any:
        """
        Update a contract's fields.

        Args:
            contract_id: The contract ID to update
            note: New note text for the contract

        Returns:
            Updated contract details
        """
        logger.info(f"Updating contract {contract_id}")
        contract: Dict[str, Any] = {"id": contract_id}
        if note is not None:
            contract["note"] = note
        return await self._request("POST", f"ClientContract", json=[contract])

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

    async def link_asset_to_ticket(
        self,
        ticket_id: int,
        asset_id: int,
    ) -> Any:
        """
        Link an asset to a ticket via the assets array.

        Args:
            ticket_id: The ticket to link the asset to
            asset_id: The asset ID to link

        Returns:
            Updated ticket details
        """
        logger.info(f"Linking asset {asset_id} to ticket {ticket_id}")
        return await self._request(
            "POST", "tickets",
            json=[{"id": ticket_id, "assets": [{"id": asset_id}]}],
        )

    async def search_assets(
        self,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        inventory_number: Optional[str] = None,
        count: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search/list assets with filters.

        Args:
            client_id: Filter by client/company ID
            user_id: Filter by user ID (assets assigned to this user)
            search: Text search filter
            inventory_number: Exact match on inventory_number (hostname)
            count: Maximum results to return

        Returns:
            List of matching assets
        """
        params: Dict[str, Any] = {
            "count": count,
            "activeinactive": "true,false",  # active only
        }
        if client_id is not None:
            params["client_id"] = client_id
        if user_id is not None:
            params["user_id"] = user_id
        if search:
            params["search"] = search
        if inventory_number:
            params["inventory_number"] = inventory_number

        result = await self._request("GET", "Asset", params=params)
        # Halo may return {"assets": [...]} or a list directly
        if isinstance(result, dict):
            assets = result.get("assets", [])
        elif isinstance(result, list):
            assets = result
        else:
            assets = []
        logger.info(f"Asset search returned {len(assets)} results")
        return assets

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
