"""
Halo PSA OAuth Token Management

Handles OAuth2 Client Credentials flow for Halo API authentication.
Automatically refreshes tokens when they expire.
"""

import time
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """OAuth token information."""
    access_token: str
    token_type: str
    expires_at: float  # Unix timestamp
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 60s buffer)."""
        return time.time() >= (self.expires_at - 60)


class HaloAuthManager:
    """Manages OAuth tokens for Halo API."""
    
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
    ):
        """
        Initialize the auth manager.
        
        Args:
            base_url: Halo instance URL (e.g., https://company.halopsa.com)
            client_id: OAuth client ID
            client_secret: OAuth client secret
        """
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[TokenInfo] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def token_url(self) -> str:
        """OAuth token endpoint URL."""
        return f"{self.base_url}/auth/token"
    
    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def get_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token string
            
        Raises:
            httpx.HTTPError: If token request fails
        """
        if self._token is None or self._token.is_expired:
            await self._refresh_token()
        
        return self._token.access_token
    
    async def _refresh_token(self):
        """Fetch a new access token from Halo."""
        logger.debug("Refreshing Halo access token")
        
        client = await self.get_http_client()
        
        response = await client.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "all",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Calculate expiration time
        expires_in = data.get("expires_in", 3600)
        expires_at = time.time() + expires_in
        
        self._token = TokenInfo(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
        )
        
        logger.debug(f"Token refreshed, expires in {expires_in}s")
