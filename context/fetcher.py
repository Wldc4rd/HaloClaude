"""
Context Fetcher - Fetches related data from Halo API.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

from halo.client import HaloClient

logger = logging.getLogger(__name__)

# In-memory cache: attachment_id -> extracted text
# Attachment IDs are immutable (new upload = new ID), so no TTL needed.
_pdf_text_cache: Dict[int, str] = {}


@dataclass
class ContextData:
    """Container for all fetched Halo context."""
    ticket: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)  # Ticket history/notes
    related_tickets: List[Dict[str, Any]] = field(default_factory=list)
    user: Optional[Dict[str, Any]] = None
    client: Optional[Dict[str, Any]] = None
    assets: List[Dict[str, Any]] = field(default_factory=list)
    contracts: List[Dict[str, Any]] = field(default_factory=list)
    contract_doc_texts: Dict[int, str] = field(default_factory=dict)  # contract_id -> PDF text
    sop_articles: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ContextFetcher:
    """Fetches ticket and related data from Halo API."""

    def __init__(
        self,
        halo_client: HaloClient,
        sop_kb_search_term: Optional[str] = None,
        max_sop_articles: int = 10,
        sop_kb_filter_tag: Optional[str] = None,
    ):
        """
        Initialize the fetcher.

        Args:
            halo_client: Initialized Halo API client
            sop_kb_search_term: Search term for SOP KB articles (None to disable)
            max_sop_articles: Maximum SOP articles to fetch
            sop_kb_filter_tag: Only inject articles whose kb_tags contain this tag (None to inject all matches)
        """
        self.halo_client = halo_client
        self.sop_kb_search_term = sop_kb_search_term
        self.max_sop_articles = max_sop_articles
        self.sop_kb_filter_tag = sop_kb_filter_tag

    async def fetch_full_context(self, ticket_id: int) -> ContextData:
        """
        Fetch ticket and all linked entities.

        Args:
            ticket_id: The ticket ID to fetch context for

        Returns:
            ContextData with ticket, actions, user, client, assets, contracts, SOPs
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

        # Step 2: Extract related tickets and IDs
        context.related_tickets = self._extract_related_tickets(context.ticket)
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

            # Fetch contracts for this client
            tasks.append(self._safe_fetch(
                self.halo_client.get_client_contracts(client_id),
                f"contracts for client {client_id}"
            ))
            task_labels.append("contracts")

        for asset_id in asset_ids:
            tasks.append(self._safe_fetch(
                self.halo_client.get_asset(asset_id),
                f"asset {asset_id}"
            ))
            task_labels.append(f"asset_{asset_id}")

        # Fetch SOP KB articles if configured
        if self.sop_kb_search_term:
            tasks.append(self._safe_fetch(
                self._fetch_sop_articles(),
                "SOP KB articles"
            ))
            task_labels.append("sop_articles")

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
                    elif label == "contracts":
                        context.contracts = result if isinstance(result, list) else []
                    elif label == "sop_articles":
                        context.sop_articles = result if isinstance(result, list) else []
                    elif label.startswith("asset_"):
                        context.assets.append(result)

        # Step 4: Fetch contract document PDFs
        if context.contracts:
            context.contract_doc_texts = await self._fetch_contract_docs(context.contracts)

        return context

    async def _fetch_sop_articles(self) -> List[Dict[str, Any]]:
        """
        Search for SOP KB articles, then fetch each individually
        to get full content (the list endpoint omits resolution).
        """
        search_results = await self.halo_client.search_kb(
            self.sop_kb_search_term,
            count=self.max_sop_articles,
        )
        if not search_results:
            return []

        # Fetch full details for each article in parallel
        detail_tasks = [
            self._safe_fetch(
                self.halo_client.get_kb_article(a["id"]),
                f"KB article {a['id']}"
            )
            for a in search_results if a.get("id")
        ]
        if not detail_tasks:
            return search_results

        results = await asyncio.gather(*detail_tasks)
        detailed = []
        for result, error in results:
            if error:
                logger.warning(error)
            elif result:
                detailed.append(result)

        if not detailed:
            return search_results

        # Filter by tag if configured
        if self.sop_kb_filter_tag:
            filtered = [
                a for a in detailed
                if self.sop_kb_filter_tag.lower() in (a.get("kb_tags", "") or "").lower()
            ]
            logger.info(
                f"Fetched {len(detailed)} SOP articles, "
                f"{len(filtered)} matched tag '{self.sop_kb_filter_tag}'"
            )
            return filtered

        logger.info(f"Fetched {len(detailed)} SOP article details")
        return detailed

    async def _fetch_contract_docs(
        self,
        contracts: List[Dict[str, Any]],
    ) -> Dict[int, str]:
        """
        Fetch and extract text from contract PDF attachments.

        Args:
            contracts: List of contract dicts (must have 'id')

        Returns:
            Dict mapping contract_id -> extracted PDF text
        """
        doc_texts: Dict[int, str] = {}

        # Fetch attachment metadata for all contracts in parallel
        attach_tasks = [
            self._safe_fetch(
                self.halo_client.get_contract_attachments(c["id"]),
                f"attachments for contract {c['id']}"
            )
            for c in contracts if c.get("id")
        ]
        contract_ids = [c["id"] for c in contracts if c.get("id")]

        if not attach_tasks:
            return doc_texts

        attach_results = await asyncio.gather(*attach_tasks)

        # For each contract, extract text from its first PDF attachment
        pdf_tasks = []
        pdf_contract_ids = []

        for contract_id, (attachments, error) in zip(contract_ids, attach_results):
            if error or not attachments:
                continue
            # Find first PDF attachment
            pdf_attach = None
            for att in attachments:
                filename = att.get("filename", "").lower()
                if filename.endswith(".pdf"):
                    pdf_attach = att
                    break
            if not pdf_attach:
                # Use first attachment if no PDF found
                pdf_attach = attachments[0] if attachments else None
            if not pdf_attach:
                continue

            attach_id = pdf_attach["id"]

            # Check cache
            if attach_id in _pdf_text_cache:
                logger.debug(f"PDF cache hit for attachment {attach_id}")
                doc_texts[contract_id] = _pdf_text_cache[attach_id]
                continue

            pdf_tasks.append(self._safe_fetch(
                self.halo_client.get_attachment_bytes(attach_id),
                f"attachment {attach_id}"
            ))
            pdf_contract_ids.append((contract_id, attach_id))

        if pdf_tasks:
            pdf_results = await asyncio.gather(*pdf_tasks)

            for (contract_id, attach_id), (pdf_bytes, error) in zip(pdf_contract_ids, pdf_results):
                if error or not pdf_bytes:
                    continue
                try:
                    text = self._extract_pdf_text(pdf_bytes)
                    if text:
                        _pdf_text_cache[attach_id] = text
                        doc_texts[contract_id] = text
                        logger.info(f"Extracted {len(text)} chars from contract {contract_id} attachment {attach_id}")
                except Exception as e:
                    logger.warning(f"Failed to extract PDF text from attachment {attach_id}: {e}")

        return doc_texts

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes using PyMuPDF."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            pages = []
            for page in doc:
                pages.append(page.get_text())
            return "\n".join(pages).strip()
        finally:
            doc.close()

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

    def _extract_related_tickets(self, ticket: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract related ticket info from ticket data."""
        related = ticket.get("related_tickets", [])
        if not isinstance(related, list):
            return []

        extracted = []
        for rt in related:
            if not isinstance(rt, dict):
                continue
            tid = rt.get("id")
            if not tid:
                continue
            status = rt.get("status_name", rt.get("status", ""))
            if isinstance(status, dict):
                status = status.get("name", "")
            extracted.append({
                "id": tid,
                "summary": rt.get("summary", ""),
                "status": status or "",
            })
        return extracted
