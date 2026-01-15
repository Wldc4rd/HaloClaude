"""
Context Fetcher - Fetches related data from Halo API.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from halo.client import HaloClient

logger = logging.getLogger(__name__)


@dataclass
class ContextData:
    """Container for all fetched Halo context."""
    ticket: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)  # Ticket history/notes
    user: Optional[Dict[str, Any]] = None
    client: Optional[Dict[str, Any]] = None
    assets: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ContextFetcher:
    """Fetches ticket and related data from Halo API."""

    def __init__(self, halo_client: HaloClient):
        """
        Initialize the fetcher.

        Args:
            halo_client: Initialized Halo API client
        """
        self.halo_client = halo_client

    async def fetch_full_context(self, ticket_id: int) -> ContextData:
        """
        Fetch ticket and all linked entities.

        Args:
            ticket_id: The ticket ID to fetch context for

        Returns:
            ContextData with ticket, actions, user, client, and assets
        """
        context = ContextData()

        # Step 1: Fetch ticket and actions in parallel
        try:
            ticket_task = self.halo_client.get_ticket(ticket_id)
            actions_task = self.halo_client.get_ticket_actions(ticket_id)

            ticket_result, actions_result = await asyncio.gather(
                ticket_task,
                actions_task,
                return_exceptions=True
            )

            if isinstance(ticket_result, Exception):
                raise ticket_result
            context.ticket = ticket_result
            logger.debug(f"Fetched ticket {ticket_id}")

            if isinstance(actions_result, Exception):
                logger.warning(f"Failed to fetch actions for ticket {ticket_id}: {actions_result}")
                context.errors.append(f"Failed to fetch ticket history: {actions_result}")
            else:
                context.actions = actions_result if actions_result else []
                logger.debug(f"Fetched {len(context.actions)} actions for ticket {ticket_id}")

        except Exception as e:
            error_msg = f"Failed to fetch ticket {ticket_id}: {e}"
            logger.warning(error_msg)
            context.errors.append(error_msg)
            return context  # Can't proceed without ticket

        # Step 2: Extract related IDs
        user_id = self._extract_user_id(context.ticket)
        client_id = self._extract_client_id(context.ticket)
        asset_ids = self._extract_asset_ids(context.ticket)

        logger.debug(f"Extracted IDs - user: {user_id}, client: {client_id}, assets: {asset_ids}")

        # Step 3: Fetch related entities in parallel
        tasks = []
        task_labels = []

        if user_id:
            tasks.append(self._safe_fetch(
                self.halo_client.get_user(user_id),
                f"user {user_id}"
            ))
            task_labels.append("user")

        if client_id:
            tasks.append(self._safe_fetch(
                self.halo_client.get_client(client_id),
                f"client {client_id}"
            ))
            task_labels.append("client")

        for asset_id in asset_ids:
            tasks.append(self._safe_fetch(
                self.halo_client.get_asset(asset_id),
                f"asset {asset_id}"
            ))
            task_labels.append(f"asset_{asset_id}")

        if tasks:
            results = await asyncio.gather(*tasks)

            for label, (result, error) in zip(task_labels, results):
                if error:
                    context.errors.append(error)
                elif result:
                    if label == "user":
                        context.user = result
                    elif label == "client":
                        context.client = result
                    elif label.startswith("asset_"):
                        context.assets.append(result)

        return context

    async def _safe_fetch(self, coro, entity_desc: str) -> tuple:
        """
        Execute a fetch coroutine with error handling.

        Args:
            coro: The coroutine to execute
            entity_desc: Description for error messages

        Returns:
            Tuple of (result, error_message)
        """
        try:
            result = await coro
            return (result, None)
        except Exception as e:
            error_msg = f"Failed to fetch {entity_desc}: {e}"
            logger.warning(error_msg)
            return (None, error_msg)

    def _extract_user_id(self, ticket: Dict[str, Any]) -> Optional[int]:
        """Extract user ID from ticket data."""
        # Try common field names
        for field_name in ["user_id", "userid", "user", "reportedby"]:
            value = ticket.get(field_name)
            if isinstance(value, int):
                return value
            if isinstance(value, dict) and value.get("id"):
                return value["id"]
        return None

    def _extract_client_id(self, ticket: Dict[str, Any]) -> Optional[int]:
        """Extract client/company ID from ticket data."""
        # Try common field names
        for field_name in ["client_id", "clientid", "client", "organisation_id"]:
            value = ticket.get(field_name)
            if isinstance(value, int):
                return value
            if isinstance(value, dict) and value.get("id"):
                return value["id"]
        return None

    def _extract_asset_ids(self, ticket: Dict[str, Any]) -> List[int]:
        """Extract all asset IDs from ticket data."""
        asset_ids = []

        # Direct asset_id field
        if ticket.get("asset_id"):
            asset_ids.append(ticket["asset_id"])

        # Assets array (various formats)
        for field_name in ["assets", "linkedassets", "asset"]:
            assets = ticket.get(field_name, [])
            if isinstance(assets, list):
                for asset in assets:
                    if isinstance(asset, dict) and asset.get("id"):
                        asset_ids.append(asset["id"])
                    elif isinstance(asset, int):
                        asset_ids.append(asset)
            elif isinstance(assets, dict) and assets.get("id"):
                asset_ids.append(assets["id"])
            elif isinstance(assets, int):
                asset_ids.append(assets)

        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for aid in asset_ids:
            if aid not in seen:
                seen.add(aid)
                unique_ids.append(aid)

        return unique_ids
