"""
MCP Tool registrations for CIPP (CyberDrain Improved Partner Portal).

Registers CIPP tools on the existing HaloClaude MCP server
so they are available to Claude Desktop and other MCP clients.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp_server.server import mcp
from .client import CippClient

logger = logging.getLogger(__name__)

# CippClient instance, set during app startup
_cipp_client: Optional[CippClient] = None


def set_cipp_client(client: CippClient) -> None:
    """Set the CIPP client instance for tools to use."""
    global _cipp_client
    _cipp_client = client


def get_cipp_client() -> CippClient:
    """Get the CIPP client, raising if not initialized."""
    if _cipp_client is None:
        raise RuntimeError("CippClient not initialized. Is CIPP_ENABLED=true?")
    return _cipp_client


# =============================================================================
# Read-only Tools (12)
# =============================================================================

@mcp.tool(
    description="List all Microsoft 365 tenants managed in CIPP. Returns tenant "
    "names, default domains, and customer IDs."
)
async def cipp_list_tenants() -> List[Dict[str, Any]]:
    """List all tenants managed in CIPP."""
    logger.info("MCP: cipp_list_tenants called")
    client = get_cipp_client()
    return await client.list_tenants()


@mcp.tool(
    description="List users in a Microsoft 365 tenant via CIPP. Returns user "
    "details including display name, UPN, email, licenses, and sign-in status."
)
async def cipp_list_users(tenant_filter: str) -> List[Dict[str, Any]]:
    """
    List users in a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_users called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_users(tenant_filter)


@mcp.tool(
    description="List groups in a Microsoft 365 tenant via CIPP. Returns security "
    "groups, distribution lists, and Microsoft 365 groups."
)
async def cipp_list_groups(tenant_filter: str) -> List[Dict[str, Any]]:
    """
    List groups in a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_groups called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_groups(tenant_filter)


@mcp.tool(
    description="List all groups a specific user belongs to in Microsoft 365 via CIPP."
)
async def cipp_list_user_groups(
    tenant_filter: str, user_id: str,
) -> List[Dict[str, Any]]:
    """
    List groups for a specific user.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        user_id: User ID (GUID or UPN)
    """
    logger.info(f"MCP: cipp_list_user_groups called for {user_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.list_user_groups(tenant_filter, user_id)


@mcp.tool(
    description="List mailboxes in a Microsoft 365 tenant via CIPP. Returns "
    "mailbox details including type, size, and archive status."
)
async def cipp_list_mailboxes(tenant_filter: str) -> List[Dict[str, Any]]:
    """
    List mailboxes in a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_mailboxes called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_mailboxes(tenant_filter)


@mcp.tool(
    description="List permissions on a specific mailbox in Microsoft 365 via CIPP. "
    "Shows Full Access, Send As, and Send on Behalf permissions."
)
async def cipp_list_mailbox_permissions(
    tenant_filter: str, user_id: str,
) -> List[Dict[str, Any]]:
    """
    List mailbox permissions.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        user_id: Mailbox owner User ID (GUID or UPN)
    """
    logger.info(f"MCP: cipp_list_mailbox_permissions called for {user_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.list_mailbox_permissions(tenant_filter, user_id)


@mcp.tool(
    description="List inbox rules for a specific mailbox in Microsoft 365 via CIPP. "
    "Critical for investigating compromised accounts (forwarding rules)."
)
async def cipp_list_mailbox_rules(
    tenant_filter: str, user_id: str,
) -> List[Dict[str, Any]]:
    """
    List inbox rules for a mailbox.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        user_id: User ID (GUID or UPN)
    """
    logger.info(f"MCP: cipp_list_mailbox_rules called for {user_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.list_mailbox_rules(tenant_filter, user_id)


@mcp.tool(
    description="List Intune managed devices in a Microsoft 365 tenant via CIPP. "
    "Returns device details including OS, compliance state, and last sync time."
)
async def cipp_list_devices(tenant_filter: str) -> List[Dict[str, Any]]:
    """
    List devices in a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_devices called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_devices(tenant_filter)


@mcp.tool(
    description="List license assignments in a Microsoft 365 tenant via CIPP. "
    "Shows available vs consumed licenses for each SKU."
)
async def cipp_list_licenses(tenant_filter: str) -> List[Dict[str, Any]]:
    """
    List licenses in a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_licenses called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_licenses(tenant_filter)


@mcp.tool(
    description="List recent sign-in logs for a Microsoft 365 tenant via CIPP. "
    "Shows sign-in activity including success/failure, location, and device info."
)
async def cipp_list_sign_ins(tenant_filter: str) -> List[Dict[str, Any]]:
    """
    List sign-in logs for a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_sign_ins called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_sign_ins(tenant_filter)


@mcp.tool(
    description="List Microsoft Defender status for devices in a Microsoft 365 "
    "tenant via CIPP. Shows AV status, signature freshness, and active threats."
)
async def cipp_list_defender_state(tenant_filter: str) -> List[Dict[str, Any]]:
    """
    List Defender state for a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_defender_state called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_defender_state(tenant_filter)


@mcp.tool(
    description="List Conditional Access policies in a Microsoft 365 tenant via CIPP. "
    "Shows policy names, states, conditions, and grant controls."
)
async def cipp_list_conditional_access_policies(
    tenant_filter: str,
) -> List[Dict[str, Any]]:
    """
    List Conditional Access policies for a tenant.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
    """
    logger.info(f"MCP: cipp_list_conditional_access_policies called for {tenant_filter}")
    client = get_cipp_client()
    return await client.list_conditional_access_policies(tenant_filter)


# =============================================================================
# Write/Action Tools (4)
# =============================================================================

@mcp.tool(
    description="Reset a user's password in Microsoft 365 via CIPP. Generates a "
    "random temporary password that the user must change on next sign-in."
)
async def cipp_reset_password(
    tenant_filter: str, user_id: str,
) -> Dict[str, Any]:
    """
    Reset a user's password.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        user_id: User ID (GUID or UPN)
    """
    logger.info(f"MCP: cipp_reset_password called for {user_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.reset_password(tenant_filter, user_id)


@mcp.tool(
    description="Disable a user account in Microsoft 365 via CIPP. Blocks sign-in "
    "and revokes active sessions."
)
async def cipp_disable_user(
    tenant_filter: str, user_id: str,
) -> Dict[str, Any]:
    """
    Disable a user account.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        user_id: User ID (GUID or UPN)
    """
    logger.info(f"MCP: cipp_disable_user called for {user_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.disable_user(tenant_filter, user_id)


@mcp.tool(
    description="Execute an action on an Intune managed device via CIPP. "
    "Actions: syncDevice, rebootNow, locateDevice, remoteLock, retireDevice."
)
async def cipp_device_action(
    tenant_filter: str,
    device_id: str,
    action: str,
) -> Dict[str, Any]:
    """
    Execute a device action.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        device_id: Intune device ID (GUID)
        action: Action to execute (syncDevice, rebootNow, locateDevice, remoteLock, retireDevice)
    """
    logger.info(f"MCP: cipp_device_action called: {action} on {device_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.device_action(tenant_filter, device_id, action)


@mcp.tool(
    description="Edit mailbox permissions in Microsoft 365 via CIPP. Add or remove "
    "Full Access, Send As, or Send on Behalf permissions."
)
async def cipp_edit_mailbox_permissions(
    tenant_filter: str,
    user_id: str,
    permissions: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Edit mailbox permissions.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        user_id: Mailbox owner User ID (GUID or UPN)
        permissions: Permission configuration dict
    """
    logger.info(f"MCP: cipp_edit_mailbox_permissions called for {user_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.edit_mailbox_permissions(tenant_filter, user_id, permissions)


@mcp.tool(
    description="Offboard a user in Microsoft 365 via CIPP's Offboarding Wizard. "
    "Performs multiple actions in one call: ConvertToShared, HideFromGAL, DeleteUser, "
    "DisableSignIn, ResetPass, RevokeSessions, RemoveGroups, RemoveLicenses, "
    "AccessAutomap/AccessNoAutomap (array of {value: UPN}), "
    "OnedriveAccess (array of {value: UPN}), OOO (string), forward ({value: UPN})."
)
async def cipp_offboard_user(
    tenant_filter: str,
    user_id: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Offboard a user via CIPP Offboarding Wizard.

    Args:
        tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)
        user_id: User UPN to offboard (e.g., user@domain.com)
        options: Offboarding options dict with boolean flags and array fields
    """
    logger.info(f"MCP: cipp_offboard_user called for {user_id} in {tenant_filter}")
    client = get_cipp_client()
    return await client.offboard_user(tenant_filter, user_id, options)
