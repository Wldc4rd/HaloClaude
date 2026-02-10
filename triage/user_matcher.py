"""
User/Client Auto-Matcher

Deterministic logic to identify the affected user and/or client from ticket
content when a ticket arrives without those fields linked (e.g. automated
alerts from Mesh, NinjaRMM, SentinelOne, etc.).

Runs as pipeline Stage 0, before triage classification.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from halo.client import HaloClient

logger = logging.getLogger(__name__)

# Email addresses to ignore (system/noreply senders).
SYSTEM_EMAIL_PATTERNS = {
    "noreply@",
    "no-reply@",
    "mailer-daemon@",
    "postmaster@",
    "donotreply@",
    "do-not-reply@",
    "notifications@",
    "alert@",
    "alerts@",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}", re.ASCII)


def is_system_user(user: Optional[Dict[str, Any]]) -> bool:
    """Check if a Halo user record looks like a system/noreply account."""
    if not user:
        return False
    email = (user.get("emailaddress") or "").lower()
    name = (user.get("name") or "").lower()
    return _is_system_email(email) or _is_system_email(name)

# Hostname pattern: sequences like SRV-DC01, PC-JSMITH, DESKTOP-ABC123.
# Must contain at least one letter, may contain hyphens, and be 3-30 chars.
# We look for these as standalone tokens (word boundaries).
HOSTNAME_RE = re.compile(
    r"\b(?=[A-Z0-9-]{3,30}\b)(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*[0-9A-Z])"
    r"[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+\b"
)


def _is_system_email(email: str) -> bool:
    """Check if an email address looks like a system/noreply address."""
    email_lower = email.lower()
    return any(pattern in email_lower for pattern in SYSTEM_EMAIL_PATTERNS)


def _extract_emails(text: str) -> List[str]:
    """Extract unique email addresses from text, filtering system addresses."""
    if not text:
        return []
    emails = EMAIL_RE.findall(text)
    seen = set()
    result = []
    for email in emails:
        email_lower = email.lower()
        if email_lower not in seen and not _is_system_email(email):
            seen.add(email_lower)
            result.append(email)
    return result


def _extract_hostnames(text: str) -> List[str]:
    """Extract candidate device hostnames from text.

    Looks for uppercase hyphenated patterns like SRV-DC01, PC-JSMITH,
    DESKTOP-ABC123, LAPTOP-001, etc.
    """
    if not text:
        return []
    # Search in uppercase version to normalize
    upper_text = text.upper()
    matches = HOSTNAME_RE.findall(upper_text)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for hostname in matches:
        if hostname not in seen:
            seen.add(hostname)
            result.append(hostname)
    return result


def _collect_ticket_text(ticket: Dict, actions: List[Dict]) -> str:
    """Gather searchable text from ticket details and action notes."""
    parts = []
    # Ticket summary and details
    if ticket.get("summary"):
        parts.append(ticket["summary"])
    if ticket.get("details"):
        parts.append(ticket["details"])
    # Action notes (ticket history)
    for action in actions:
        if action.get("note"):
            parts.append(action["note"])
        if action.get("who"):
            parts.append(action["who"])
    return "\n".join(parts)


async def find_and_link_user_or_client(
    ticket_id: int,
    ticket: Dict[str, Any],
    actions: List[Dict[str, Any]],
    halo_client: HaloClient,
) -> Optional[Dict[str, Any]]:
    """
    Attempt to identify and link the affected user and/or client to a ticket.

    Strategy 1: Extract email addresses from ticket content, search Halo
    for matching users. Links both user and client.

    Strategy 2 (fallback): Extract device hostnames from ticket content,
    search Halo for matching assets. Links client (and asset) only.

    Returns a dict with "user" and/or "client" and/or "asset" keys if
    a match was found, or None if no match.
    """
    logger.info(f"User/client resolution starting for ticket {ticket_id}")

    text = _collect_ticket_text(ticket, actions)
    if not text.strip():
        logger.info(f"Ticket {ticket_id} has no searchable text")
        return None

    # === Strategy 1: Email address matching ===
    emails = _extract_emails(text)
    if emails:
        logger.info(
            f"Extracted {len(emails)} candidate email(s) from ticket {ticket_id}: "
            f"{emails[:5]}"
        )
        for email in emails:
            user = await _try_email_match(email, halo_client)
            if user:
                user_id = user.get("id")
                client_id = _extract_client_id_from_user(user)
                user_name = user.get("name", "")

                logger.info(
                    f"Email match: '{email}' -> user {user_id} ({user_name}), "
                    f"client {client_id}"
                )

                # Link user and client to ticket
                update_kwargs = {"user_id": user_id}
                if client_id:
                    update_kwargs["client_id"] = client_id

                await halo_client.update_ticket(
                    ticket_id=ticket_id, **update_kwargs
                )

                result = {"user": user}
                if client_id:
                    result["client_id"] = client_id
                return result

    # === Strategy 2: Device/hostname matching (client only) ===
    hostnames = _extract_hostnames(text)
    if hostnames:
        logger.info(
            f"Extracted {len(hostnames)} candidate hostname(s) from ticket "
            f"{ticket_id}: {hostnames[:5]}"
        )
        for hostname in hostnames:
            asset = await _try_hostname_match(hostname, halo_client)
            if asset:
                asset_id = asset.get("id")
                client_id = _extract_client_id_from_asset(asset)
                asset_name = (
                    asset.get("inventory_number")
                    or asset.get("key_field")
                    or f"Asset {asset_id}"
                )

                logger.info(
                    f"Hostname match: '{hostname}' -> asset {asset_id} "
                    f"({asset_name}), client {client_id}"
                )

                if client_id:
                    await halo_client.update_ticket(
                        ticket_id=ticket_id, client_id=client_id
                    )
                    await halo_client.link_asset_to_ticket(
                        ticket_id=ticket_id, asset_id=asset_id
                    )
                    return {"asset": asset, "client_id": client_id}

    logger.info(f"User/client resolution: no match found for ticket {ticket_id}")
    return None


async def _try_email_match(
    email: str,
    halo_client: HaloClient,
) -> Optional[Dict[str, Any]]:
    """Search Halo users by email and return the best match."""
    try:
        users = await halo_client.search_users(search=email, count=5)
    except Exception as e:
        logger.warning(f"User search for '{email}' failed: {e}")
        return None

    if not users:
        return None

    # Prefer exact email match
    email_lower = email.lower()
    for user in users:
        user_email = (user.get("emailaddress") or "").lower()
        if user_email == email_lower:
            return user

    # If only one result, use it even without exact match
    # (Halo search is fuzzy so the email might be stored differently)
    if len(users) == 1:
        return users[0]

    return None


async def _try_hostname_match(
    hostname: str,
    halo_client: HaloClient,
) -> Optional[Dict[str, Any]]:
    """Search Halo assets by hostname and return a match if unambiguous."""
    try:
        assets = await halo_client.search_assets(search=hostname, count=5)
    except Exception as e:
        logger.warning(f"Asset search for '{hostname}' failed: {e}")
        return None

    if not assets:
        return None

    # Look for exact match on inventory_number, key_field, or hostname
    hostname_upper = hostname.upper()
    for asset in assets:
        for field in ("inventory_number", "key_field", "hostname"):
            value = (asset.get(field) or "").upper().strip()
            if value == hostname_upper:
                return asset

    # If single result, use it
    if len(assets) == 1:
        return assets[0]

    return None


def _extract_client_id_from_user(user: Dict[str, Any]) -> Optional[int]:
    """Extract client ID from a Halo user record."""
    client_id = user.get("client_id")
    if isinstance(client_id, int):
        return client_id
    if isinstance(client_id, dict):
        return client_id.get("id")
    return None


def _extract_client_id_from_asset(asset: Dict[str, Any]) -> Optional[int]:
    """Extract client ID from a Halo asset record."""
    client_id = asset.get("client_id")
    if isinstance(client_id, int):
        return client_id
    if isinstance(client_id, dict):
        return client_id.get("id")
    return None
