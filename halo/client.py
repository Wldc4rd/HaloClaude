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
            self._http_client = httpx.AsyncClient()
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
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        result = await self._request("GET", f"tickets/{ticket_id}", params={
            "includedetails": "true",
        })
        return result.get("actions", [])
    
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
