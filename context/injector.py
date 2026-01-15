"""
Context Injector - Orchestrates context parsing, fetching, and injection.
"""

import logging
import time
from typing import Dict, Optional, Tuple

from halo.client import HaloClient
from .parser import TicketIdParser
from .fetcher import ContextFetcher, ContextData
from .formatter import ContextFormatter

logger = logging.getLogger(__name__)


class ContextInjector:
    """
    Orchestrates automatic context injection for Claude.

    Parses ticket ID from system prompts, fetches related data from Halo,
    and injects formatted context back into the system prompt.
    """

    def __init__(
        self,
        halo_client: HaloClient,
        enabled: bool = True,
        cache_ttl: int = 300,
    ):
        """
        Initialize the context injector.

        Args:
            halo_client: Initialized Halo API client
            enabled: Whether context injection is enabled
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self.halo_client = halo_client
        self.enabled = enabled
        self.cache_ttl = cache_ttl

        self.parser = TicketIdParser()
        self.fetcher = ContextFetcher(halo_client)
        self.formatter = ContextFormatter()

        # Simple in-memory cache: {ticket_id: (ContextData, timestamp)}
        self._cache: Dict[int, Tuple[ContextData, float]] = {}

    async def inject_context(self, system_prompt: Optional[str]) -> Optional[str]:
        """
        Parse ticket ID, fetch context, and inject into system prompt.

        Args:
            system_prompt: The original system prompt from Halo

        Returns:
            Modified system prompt with injected context,
            or original if injection fails/disabled/no ticket found
        """
        if not self.enabled:
            logger.debug("Context injection disabled")
            return system_prompt

        if not system_prompt:
            logger.debug("No system prompt to inject into")
            return system_prompt

        # Parse ticket ID from system prompt
        ticket_id = self.parser.parse(system_prompt)
        if not ticket_id:
            logger.debug("No ticket ID found in system prompt")
            return system_prompt

        logger.info(f"Injecting context for ticket {ticket_id}")

        try:
            # Get context (from cache or fresh fetch)
            context = await self._get_or_fetch_context(ticket_id)

            # Format context for injection
            formatted = self.formatter.format(context)

            # Inject at the end of system prompt
            injected = f"{system_prompt}\n\n{formatted}"

            logger.debug(f"Successfully injected context for ticket {ticket_id}")
            return injected

        except Exception as e:
            logger.warning(f"Context injection failed for ticket {ticket_id}: {e}")
            # Graceful degradation - return original prompt
            return system_prompt

    async def _get_or_fetch_context(self, ticket_id: int) -> ContextData:
        """
        Get context from cache or fetch fresh.

        Args:
            ticket_id: The ticket ID to get context for

        Returns:
            ContextData for the ticket
        """
        now = time.time()

        # Check cache
        if ticket_id in self._cache:
            context, cached_at = self._cache[ticket_id]
            if now - cached_at < self.cache_ttl:
                logger.debug(f"Using cached context for ticket {ticket_id}")
                return context
            else:
                logger.debug(f"Cache expired for ticket {ticket_id}")

        # Fetch fresh
        logger.debug(f"Fetching fresh context for ticket {ticket_id}")
        context = await self.fetcher.fetch_full_context(ticket_id)

        # Update cache
        self._cache[ticket_id] = (context, now)

        # Clean old cache entries (simple cleanup)
        self._cleanup_cache(now)

        return context

    def _cleanup_cache(self, now: float):
        """Remove expired cache entries."""
        expired = [
            tid for tid, (_, cached_at) in self._cache.items()
            if now - cached_at >= self.cache_ttl
        ]
        for tid in expired:
            del self._cache[tid]

    def clear_cache(self):
        """Clear all cached context."""
        self._cache.clear()
        logger.debug("Context cache cleared")
