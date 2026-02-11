"""
User/Client Auto-Matcher

Identifies the affected user and/or client from ticket content when a ticket
arrives without those fields linked (e.g. automated alerts from Mesh,
NinjaRMM, SentinelOne, etc.).

Extraction strategies (in order):
  1. Email address → Halo user search
  2. Regex hostname patterns → Halo asset search → NinjaRMM fallback
  3. Broad all-caps tokens → NinjaRMM device search (skipped if text is
     mostly uppercase to avoid false positives)
  4. AI extraction → Claude picks out the hostname from context

Runs as pipeline Stage 0, before triage classification.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import anthropic

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

# Hostname patterns — three categories:
#
# 1. Hyphenated: DESKTOP-ABC123, SRV-DC01, KM-FRONTDESK, BEN-LAPTOP-1
#    Any uppercase sequence with at least one hyphen-separated segment.
#
# 2. Underscore-separated: BACK_OFFICE, BEN_LAPTOP
#    Same as hyphenated but with underscores.
#
# 3. Known-prefix non-hyphenated: ADVISORTAB1, PC12, SRVSQL01
#    Common computer-type prefixes followed by alphanumerics.
#    Must have at least one char after the prefix to avoid bare words.
#
# NOTE: Many real hostnames are single words (ACCOUNTING, SHERRI, BASSMAN)
# that can't be reliably extracted via regex.  Those are handled by the
# NinjaRMM search fallback in _try_hostname_match instead.
_HYPHENATED_HOSTNAME_RE = re.compile(
    r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+\b"
)
_UNDERSCORE_HOSTNAME_RE = re.compile(
    r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b"
)
_BARE_HOSTNAME_PREFIXES = (
    "DESKTOP", "LAPTOP", "NOTEBOOK", "SERVER", "SRV", "PC",
    "WORKSTATION", "WKST", "WS",
)
_BARE_HOSTNAME_RE = re.compile(
    r"\b(?:" + "|".join(_BARE_HOSTNAME_PREFIXES) + r")"
    r"[A-Z0-9]+\b"
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

    Looks for:
      - Hyphenated patterns: DESKTOP-ABC123, SRV-DC01, KM-FRONTDESK
      - Underscore patterns: BACK_OFFICE, BEN_LAPTOP
      - Known-prefix patterns: PC12, SRVSQL01, ADVISORTAB1
    """
    if not text:
        return []
    # Search in uppercase version to normalize
    upper_text = text.upper()
    matches = _HYPHENATED_HOSTNAME_RE.findall(upper_text)
    matches.extend(_UNDERSCORE_HOSTNAME_RE.findall(upper_text))
    matches.extend(_BARE_HOSTNAME_RE.findall(upper_text))
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


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ALLCAPS_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,29}\b")

# Tokens that frequently appear in all-caps in ticket HTML/text but are
# never hostnames.  Kept small — NinjaRMM exact-match is the real filter.
_CAPS_STOPWORDS = frozenset({
    # HTML remnants / common markup
    "HTML", "HEAD", "BODY", "DIV", "SPAN", "TABLE", "TBODY", "THEAD",
    "STYLE", "SCRIPT", "FONT", "CENTER", "STRONG", "BLOCKQUOTE",
    "FORM", "INPUT", "BUTTON", "LABEL", "SECTION", "HEADER", "FOOTER",
    # Very common English words
    "THE", "AND", "FOR", "NOT", "BUT", "ALL", "NEW", "NOW", "ARE",
    "WAS", "HAS", "HAD", "CAN", "DID", "GET", "GOT", "MAY", "SAY",
    "THIS", "THAT", "WITH", "FROM", "HAVE", "BEEN", "WILL", "DOES",
    "THEY", "WHAT", "WHEN", "WHICH", "THEIR", "THERE", "YOUR",
    "WOULD", "COULD", "SHOULD", "ABOUT", "AFTER", "OTHER",
    "THESE", "THOSE", "SOME", "THAN", "INTO", "JUST", "ALSO",
    "EACH", "EVEN", "ONLY", "OVER", "SUCH", "VERY", "LIKE",
    "THEN", "MAKE", "MADE", "FIND", "HERE", "KNOW", "TAKE",
    "COME", "WANT", "LOOK", "NEED", "WORK", "CALL", "BACK",
    "BEEN", "MUCH", "MUST", "WELL", "STILL", "SINCE", "BOTH",
    "SURE", "SAME", "MOST", "SENT", "DEAR", "HELP", "PLEASE",
    "THANKS", "THANK", "HELLO", "REGARDS",
    # Ticket / status terms
    "OPEN", "CLOSED", "PENDING", "RESOLVED", "ASSIGNED", "TICKET",
    "NOTE", "ACTION", "UPDATE", "STATUS", "EMAIL", "USER", "CLIENT",
    "AGENT", "SUBJECT", "DETAILS", "SUMMARY", "PRIORITY",
    "HIGH", "LOW", "MEDIUM", "CRITICAL", "URGENT",
    # IT / OS / vendor terms
    "CPU", "RAM", "SSD", "HDD", "USB", "GPU", "DNS", "DHCP",
    "HTTP", "HTTPS", "FTP", "SSH", "SSL", "TLS", "VPN", "RDP",
    "BIOS", "RAID", "MFA", "SSO", "MDM", "API", "SQL", "PDF",
    "WINDOWS", "LINUX", "MACOS", "MICROSOFT", "GOOGLE", "APPLE",
    "DELL", "LENOVO", "OUTLOOK", "TEAMS", "OFFICE", "AZURE",
    "INTUNE", "DEFENDER", "SENTINEL", "ERROR", "ALERT", "WARNING",
    "FAILED", "SUCCESS", "OFFLINE", "ONLINE", "NETWORK", "SERVICE",
    "MEMORY", "DISK", "SYSTEM", "SOFTWARE", "INSTALL", "VERSION",
    "DEVICE", "COMPUTER", "PHONE", "MOBILE", "PRINTER", "MONITOR",
    "DOMAIN", "LOCAL", "ADMIN", "PASSWORD", "RESET", "ACCESS",
    "ACCOUNT", "LOCKED", "DISABLED", "ENABLED",
    # Words that appear when a ticket discusses a workstation/issue
    "WORKSTATION", "REBOOT", "RESTART", "ISSUE", "PROBLEM", "BROKEN",
    "NEEDS", "RUNNING", "SLOW", "CRASH", "FROZEN", "STUCK",
    "SCREEN", "BLUE", "BLACK", "LOGIN", "LOGON", "LOGOUT",
    "STARTUP", "SHUTDOWN", "BOOT", "DRIVE", "FILE", "FOLDER",
    "BACKUP", "RESTORE", "WIFI", "INTERNET", "BROWSER", "CHROME",
    "FIREFOX", "EDGE", "ADOBE", "ZOOM", "SLACK",
    # Monitoring / vendor tool names
    "NINJARMM", "NINJA", "DATTO", "SENTINELONE", "TODYL",
    "CONNECTWISE", "AUTOMATE", "ZORUS", "MESH",
})


def _extract_allcaps_tokens(text: str, exclude: set) -> List[str]:
    """Extract all-caps tokens as broad hostname candidates.

    Strips HTML, pulls uppercase tokens 3-30 chars, filters stopwords
    and any tokens already found by hostname regex.
    Skips entirely if the text is mostly uppercase (e.g. user typed in caps).

    Returns up to 15 candidate tokens.
    """
    if not text:
        return []

    # Check caps ratio — if >40% of alpha chars are uppercase, skip
    alpha_chars = [c for c in text if c.isalpha()]
    if alpha_chars:
        upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if upper_ratio > 0.40:
            logger.debug(
                f"Skipping broad caps extraction: {upper_ratio:.0%} uppercase"
            )
            return []

    # Strip HTML tags, then uppercase
    cleaned = _HTML_TAG_RE.sub(" ", text)
    upper_text = cleaned.upper()

    tokens = _ALLCAPS_TOKEN_RE.findall(upper_text)

    seen = set()
    result = []
    for token in tokens:
        if (
            token not in seen
            and token not in exclude
            and token not in _CAPS_STOPWORDS
        ):
            seen.add(token)
            result.append(token)
            if len(result) >= 15:
                break
    return result


async def _ai_extract_hostname(
    text: str,
    anthropic_client: anthropic.AsyncAnthropic,
    model: str,
) -> Optional[str]:
    """Ask Claude to extract a computer hostname from ticket text.

    Returns the hostname string, or None if Claude doesn't find one.
    """
    # Truncate text to avoid huge context for this simple extraction
    truncated = text[:4000] if len(text) > 4000 else text

    try:
        response = await anthropic_client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    "Extract the computer hostname or device name from this IT "
                    "support ticket text. Look for the machine name that the "
                    "ticket is about (e.g. DESKTOP-ABC123, SHERRI, BASSMAN, "
                    "ACCOUNTING, PC7, etc.).\n\n"
                    "Respond with ONLY the hostname in uppercase, or NONE if "
                    "no hostname is found.\n\n"
                    f"TICKET TEXT:\n{truncated}"
                ),
            }],
        )
        hostname = response.content[0].text.strip().upper()
        if hostname and hostname != "NONE" and len(hostname) <= 30:
            logger.info(f"AI extracted hostname: '{hostname}'")
            return hostname
    except Exception as e:
        logger.warning(f"AI hostname extraction failed: {e}")

    return None


async def find_and_link_user_or_client(
    ticket_id: int,
    ticket: Dict[str, Any],
    actions: List[Dict[str, Any]],
    halo_client: HaloClient,
    ninja_client: Optional[Any] = None,
    anthropic_client: Optional[anthropic.AsyncAnthropic] = None,
    model: str = "claude-sonnet-4-5-20250929",
) -> Optional[Dict[str, Any]]:
    """
    Attempt to identify and link the affected user and/or client to a ticket.

    Strategy 1: Email addresses → Halo user search
    Strategy 2: Regex hostnames → Halo asset search → NinjaRMM fallback
    Strategy 3: Broad all-caps tokens → NinjaRMM device search
    Strategy 4: AI extraction → Claude picks hostname → Halo/NinjaRMM search

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

    # === Strategy 2: Regex hostname matching ===
    hostnames = _extract_hostnames(text)
    if hostnames:
        logger.info(
            f"Extracted {len(hostnames)} candidate hostname(s) from ticket "
            f"{ticket_id}: {hostnames[:5]}"
        )
        result = await _try_hostnames_and_link(
            ticket_id, hostnames, halo_client, ninja_client, ticket_text=text
        )
        if result:
            return result

    # === Strategy 3: Broad all-caps tokens → NinjaRMM (only if available) ===
    if ninja_client:
        already_tried = set(hostnames) if hostnames else set()
        caps_tokens = _extract_allcaps_tokens(text, exclude=already_tried)
        if caps_tokens:
            logger.info(
                f"Trying {len(caps_tokens)} broad caps token(s) against NinjaRMM "
                f"for ticket {ticket_id}: {caps_tokens[:5]}"
            )
            for token in caps_tokens:
                asset = await _try_ninja_hostname_search(
                    token, token, halo_client, ninja_client
                )
                if asset:
                    return await _link_hostname_match(
                        ticket_id, token, asset, halo_client, text
                    )

    # === Strategy 4: AI hostname extraction (final fallback) ===
    if anthropic_client:
        ai_hostname = await _ai_extract_hostname(text, anthropic_client, model)
        if ai_hostname:
            already_tried = set(hostnames) if hostnames else set()
            if ai_hostname not in already_tried:
                logger.info(
                    f"AI extracted hostname '{ai_hostname}' for ticket "
                    f"{ticket_id}, searching Halo/NinjaRMM"
                )
                asset = await _try_hostname_match(
                    ai_hostname, halo_client, ninja_client
                )
                if asset:
                    return await _link_hostname_match(
                        ticket_id, ai_hostname, asset, halo_client, text
                    )

    logger.info(f"User/client resolution: no match found for ticket {ticket_id}")
    return None


async def _try_hostnames_and_link(
    ticket_id: int,
    hostnames: List[str],
    halo_client: HaloClient,
    ninja_client: Optional[Any],
    ticket_text: str = "",
) -> Optional[Dict[str, Any]]:
    """Try a list of hostname candidates against Halo/NinjaRMM and link."""
    for hostname in hostnames:
        asset = await _try_hostname_match(hostname, halo_client, ninja_client)
        if asset:
            return await _link_hostname_match(
                ticket_id, hostname, asset, halo_client, ticket_text
            )
    return None


async def _link_hostname_match(
    ticket_id: int,
    hostname: str,
    asset: Dict[str, Any],
    halo_client: HaloClient,
    ticket_text: str = "",
) -> Optional[Dict[str, Any]]:
    """Link a matched asset to the ticket and return the resolution dict.

    Also attempts to resolve the correct user under the asset's client
    so that tickets from vendor accounts (e.g. Zorus) get the real user set.
    """
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
        # Try to resolve the correct user under this client
        resolved_user = await _try_resolve_user_for_client(
            client_id, ticket_text, halo_client, asset=asset
        )

        update_kwargs: Dict[str, Any] = {"client_id": client_id}
        if resolved_user:
            update_kwargs["user_id"] = resolved_user.get("id")
            logger.info(
                f"Resolved user for client {client_id}: "
                f"{resolved_user.get('name')} (id={resolved_user.get('id')})"
            )

        await halo_client.update_ticket(ticket_id=ticket_id, **update_kwargs)
        await halo_client.link_asset_to_ticket(
            ticket_id=ticket_id, asset_id=asset_id
        )

        result: Dict[str, Any] = {"asset": asset, "client_id": client_id}
        if resolved_user:
            result["user"] = resolved_user
        return result

    return None


async def _try_resolve_user_for_client(
    client_id: int,
    ticket_text: str,
    halo_client: HaloClient,
    asset: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Try to find the correct user under a client.

    Resolution order:
      1. Single active non-system user → use them directly.
      2. Name from ticket text appears in user list.
      3. Asset's username or last-logged-in-user matches a user.
    """
    try:
        users = await halo_client.get_client_users(client_id, count=20)
    except Exception as e:
        logger.warning(f"Failed to get users for client {client_id}: {e}")
        return None

    if not users:
        return None

    # Filter to active, non-system users
    real_users = [
        u for u in users
        if not u.get("inactive") and not is_system_user(u)
    ]

    if not real_users:
        return None

    # Single user → use them
    if len(real_users) == 1:
        return real_users[0]

    # Multiple users → try name matching against ticket text
    if ticket_text:
        text_lower = ticket_text.lower()
        for user in real_users:
            name = (user.get("name") or "").strip()
            if name and len(name) > 2 and name.lower() in text_lower:
                return user

    # Try matching from the asset's username or last-logged-in-user fields
    if asset:
        asset_usernames = set()

        # Direct username field on the asset
        username = (asset.get("username") or "").strip()
        if username:
            asset_usernames.add(username.lower())

        # Check asset custom fields for "Last Logged In User"
        for field in asset.get("fields", []):
            if field.get("name") in ("Last Logged In User", "last_logged_in_user"):
                value = (field.get("value") or "").strip()
                if value:
                    # Strip domain prefix (DOMAIN\user or AzureAD\user)
                    if "\\" in value:
                        value = value.split("\\", 1)[1]
                    asset_usernames.add(value.lower())

        if asset_usernames:
            from .asset_matcher import _name_matches_user
            for user in real_users:
                user_name = (user.get("name") or "").strip()
                user_email = user.get("emailaddress")
                for device_user in asset_usernames:
                    if _name_matches_user(device_user, user_name, user_email):
                        logger.info(
                            f"User resolved via asset username: "
                            f"'{device_user}' matches '{user_name}'"
                        )
                        return user

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
    ninja_client: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """Search for a Halo asset matching this hostname.

    Strategy:
      1. Search Halo by inventory_number (exact) + text search (fuzzy).
      2. If no match and NinjaRMM is available, search NinjaRMM for the
         hostname, then find the Halo asset with a matching ninjarmm_id.
    """
    hostname_upper = hostname.upper()

    # --- Halo search: try exact inventory_number first, then text search ---
    asset = await _try_halo_hostname_search(hostname, hostname_upper, halo_client)
    if asset:
        return asset

    # --- NinjaRMM fallback: search by hostname, cross-reference to Halo ---
    if ninja_client:
        asset = await _try_ninja_hostname_search(
            hostname, hostname_upper, halo_client, ninja_client
        )
        if asset:
            return asset

    return None


async def _try_halo_hostname_search(
    hostname: str,
    hostname_upper: str,
    halo_client: HaloClient,
) -> Optional[Dict[str, Any]]:
    """Search Halo assets by hostname using inventory_number and text search."""
    try:
        assets = await halo_client.search_assets(search=hostname, count=5)
    except Exception as e:
        logger.warning(f"Asset search for '{hostname}' failed: {e}")
        return None

    if not assets:
        return None

    # Look for exact match on inventory_number, key_field, or hostname
    for asset in assets:
        for field in ("inventory_number", "key_field", "hostname"):
            value = (asset.get(field) or "").upper().strip()
            if value == hostname_upper:
                return asset

    # If single result, use it
    if len(assets) == 1:
        return assets[0]

    return None


async def _try_ninja_hostname_search(
    hostname: str,
    hostname_upper: str,
    halo_client: HaloClient,
    ninja_client: Any,
) -> Optional[Dict[str, Any]]:
    """Search NinjaRMM for a device by hostname, then find the Halo asset."""
    try:
        ninja_devices = await ninja_client.search_devices(hostname, limit=5)
    except Exception as e:
        logger.warning(f"NinjaRMM search for '{hostname}' failed: {e}")
        return None

    if not ninja_devices:
        return None

    # Find the exact match in NinjaRMM results
    ninja_device_id = None
    for device in ninja_devices:
        system_name = (device.get("systemName") or "").upper()
        display_name = (device.get("displayName") or "").upper()
        if system_name == hostname_upper or display_name == hostname_upper:
            ninja_device_id = device.get("id")
            break

    if not ninja_device_id:
        return None

    logger.info(
        f"NinjaRMM found device {ninja_device_id} for hostname '{hostname}', "
        f"searching Halo for matching asset"
    )

    # Search Halo assets for one with this ninjarmm_id.
    # Use integration_type filter to narrow results, then check ninjarmm_id.
    try:
        assets = await halo_client.search_assets(count=200)
    except Exception as e:
        logger.warning(f"Halo asset fetch for NinjaRMM cross-ref failed: {e}")
        return None

    for asset in assets:
        if asset.get("ninjarmm_id") == ninja_device_id:
            logger.info(
                f"NinjaRMM cross-ref: device {ninja_device_id} -> "
                f"Halo asset {asset.get('id')} "
                f"({asset.get('inventory_number')})"
            )
            return asset

    logger.debug(
        f"NinjaRMM device {ninja_device_id} found but no Halo asset "
        f"with matching ninjarmm_id"
    )
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
