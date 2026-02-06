"""
Asset Auto-Matcher

Deterministic logic to identify a user's workstation and link it to a ticket.
Runs as a pipeline stage between contract enrichment and technical triage.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from halo.client import HaloClient

if TYPE_CHECKING:
    from ninja.client import NinjaClient

logger = logging.getLogger(__name__)

# Asset type names that represent workstations/computers.
WORKSTATION_TYPE_KEYWORDS = {
    "workstation", "desktop", "laptop", "notebook", "computer", "pc",
}


def _is_workstation(asset: Dict[str, Any]) -> bool:
    """Check if an asset is a workstation based on its type name."""
    type_name = asset.get("assettype_name", "")
    if not type_name:
        assettype = asset.get("assettype")
        if isinstance(assettype, dict):
            type_name = assettype.get("name", "")
        elif isinstance(assettype, str):
            type_name = assettype
    if not type_name:
        return False
    return any(kw in type_name.lower() for kw in WORKSTATION_TYPE_KEYWORDS)


def _name_matches_user(
    device_user_str: str,
    user_name: str,
    user_email: Optional[str] = None,
) -> bool:
    """
    Check if a device username string plausibly matches the ticket user.

    Handles formats like:
      - "DOMAIN\\firstname.lastname"
      - "firstname.lastname"
      - "FirstName LastName"
      - "flastname" (first initial + last name)
    """
    if not device_user_str or not user_name:
        return False

    device_lower = device_user_str.lower().strip()
    # Strip domain prefix (DOMAIN\user)
    if "\\" in device_lower:
        device_lower = device_lower.split("\\", 1)[1]

    user_lower = user_name.lower().strip()
    parts = user_lower.split()

    if len(parts) < 2:
        return parts[0] in device_lower

    first = parts[0]
    last = parts[-1]

    # Exact patterns: "first.last", "first last", "firstlast", reversed
    if device_lower in (
        f"{first}.{last}",
        f"{first} {last}",
        f"{first}{last}",
        f"{last}.{first}",
        f"{last} {first}",
        f"{last}{first}",
    ):
        return True

    # "flast" pattern (first initial + last name)
    if device_lower == f"{first[0]}{last}":
        return True

    # Email prefix match
    if user_email:
        email_prefix = user_email.lower().split("@")[0]
        if device_lower == email_prefix:
            return True

    # Both first and last name appear in the string
    if first in device_lower and last in device_lower:
        return True

    return False


async def find_and_link_workstation(
    ticket_id: int,
    user_id: int,
    user_name: str,
    user_email: Optional[str],
    client_id: int,
    halo_client: HaloClient,
    ninja_client: Optional["NinjaClient"] = None,
) -> Optional[Dict[str, Any]]:
    """
    Attempt to find the user's workstation and link it to the ticket.

    Strategy (in order):
      1. Query Halo for assets assigned to this user_id, filter to workstations.
      2. Query all client workstation assets and use NinjaRMM last-logged-on-user.
      3. Search asset names for the user's name.

    Returns the matched asset dict, or None if no match found.
    """
    logger.info(
        f"Asset auto-match starting for ticket {ticket_id}: "
        f"user={user_name} (id={user_id}), client={client_id}"
    )

    # === Strategy 1: Assets assigned to this user ===
    matched = await _try_user_assigned_assets(
        user_id, client_id, user_name, user_email, halo_client
    )
    if matched:
        await _link_asset_to_ticket(ticket_id, matched, halo_client, "user_assignment")
        return matched

    # === Strategy 2: NinjaRMM last-logged-on-user matching ===
    if ninja_client:
        matched = await _try_ninja_last_user_match(
            client_id, user_name, user_email, halo_client, ninja_client
        )
        if matched:
            await _link_asset_to_ticket(ticket_id, matched, halo_client, "ninja_last_user")
            return matched

    # === Strategy 3: Asset name contains user name ===
    matched = await _try_asset_name_match(
        client_id, user_name, halo_client
    )
    if matched:
        await _link_asset_to_ticket(ticket_id, matched, halo_client, "name_match")
        return matched

    logger.info(
        f"Asset auto-match: no workstation found for user {user_name} "
        f"on ticket {ticket_id}"
    )
    return None


async def _try_user_assigned_assets(
    user_id: int,
    client_id: int,
    user_name: str,
    user_email: Optional[str],
    halo_client: HaloClient,
) -> Optional[Dict[str, Any]]:
    """Strategy 1: Find workstation assets assigned to this user in Halo."""
    try:
        assets = await halo_client.search_assets(
            user_id=user_id,
            client_id=client_id,
        )
    except Exception as e:
        logger.warning(f"Asset search by user_id failed: {e}")
        return None

    workstations = [a for a in assets if _is_workstation(a)]
    logger.info(
        f"User-assigned assets: {len(assets)} total, "
        f"{len(workstations)} workstations"
    )

    if not workstations:
        return None

    if len(workstations) == 1:
        return workstations[0]

    # Multiple: prefer one with NinjaRMM link (actively managed)
    ninja_linked = [a for a in workstations if a.get("ninjarmm_id")]
    if len(ninja_linked) == 1:
        return ninja_linked[0]

    # Still multiple: prefer one whose name matches the user
    for a in workstations:
        key = a.get("inventory_number", "") or a.get("key_field", "")
        if _name_matches_user(key, user_name, user_email):
            return a

    # Last resort: return first NinjaRMM-linked or just first
    return ninja_linked[0] if ninja_linked else workstations[0]


async def _try_ninja_last_user_match(
    client_id: int,
    user_name: str,
    user_email: Optional[str],
    halo_client: HaloClient,
    ninja_client: "NinjaClient",
) -> Optional[Dict[str, Any]]:
    """
    Strategy 2: Get client workstations with NinjaRMM IDs,
    then check last-logged-on-user for each to find a match.
    """
    try:
        assets = await halo_client.search_assets(
            client_id=client_id,
            count=100,
        )
    except Exception as e:
        logger.warning(f"Asset search by client_id failed: {e}")
        return None

    ninja_workstations = [
        a for a in assets
        if _is_workstation(a) and a.get("ninjarmm_id")
    ]

    if not ninja_workstations:
        logger.debug("No NinjaRMM-linked workstations found for client")
        return None

    logger.info(
        f"Checking NinjaRMM last-user for {len(ninja_workstations)} workstations"
    )

    # Cap at 10 to avoid excessive API calls
    ninja_workstations = ninja_workstations[:10]

    async def check_device(asset: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        ninja_id = asset["ninjarmm_id"]
        try:
            last_user = await ninja_client.get_device_last_user(ninja_id)
            # NinjaRMM may return different field names
            device_username = (
                last_user.get("userName")
                or last_user.get("username")
                or last_user.get("user")
                or ""
            )
            if _name_matches_user(device_username, user_name, user_email):
                logger.info(
                    f"NinjaRMM match: device {ninja_id} last user "
                    f"'{device_username}' matches '{user_name}'"
                )
                return (asset, True)
        except Exception as e:
            logger.debug(
                f"Failed to get last user for NinjaRMM device {ninja_id}: {e}"
            )
        return (asset, False)

    results = await asyncio.gather(
        *(check_device(a) for a in ninja_workstations),
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, Exception):
            continue
        asset, matched = result
        if matched:
            return asset

    return None


async def _try_asset_name_match(
    client_id: int,
    user_name: str,
    halo_client: HaloClient,
) -> Optional[Dict[str, Any]]:
    """
    Strategy 3: Search client assets by user's name, looking for
    workstations whose name/hostname contains the user name.
    """
    parts = user_name.strip().split()
    if len(parts) < 2:
        return None

    # Search using last name (more unique than first)
    search_term = parts[-1]

    try:
        assets = await halo_client.search_assets(
            client_id=client_id,
            search=search_term,
            count=20,
        )
    except Exception as e:
        logger.warning(f"Asset name search failed: {e}")
        return None

    workstations = [a for a in assets if _is_workstation(a)]
    if not workstations:
        return None

    for ws in workstations:
        name = (
            ws.get("inventory_number", "")
            or ws.get("key_field", "")
            or ws.get("hostname", "")
            or ""
        )
        if _name_matches_user(name, user_name):
            return ws

    return None


async def _link_asset_to_ticket(
    ticket_id: int,
    asset: Dict[str, Any],
    halo_client: HaloClient,
    match_method: str,
) -> None:
    """Link the identified asset to the ticket via Halo API."""
    asset_id = asset.get("id")
    asset_name = (
        asset.get("inventory_number")
        or asset.get("key_field")
        or f"Asset {asset_id}"
    )

    logger.info(
        f"Asset auto-match: linking asset {asset_id} ({asset_name}) "
        f"to ticket {ticket_id} (method: {match_method})"
    )

    await halo_client.link_asset_to_ticket(ticket_id=ticket_id, asset_id=asset_id)
