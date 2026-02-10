"""
CIPP Tool Definitions for Claude

Defines the tools that Claude can use to manage Microsoft 365 tenants
via CIPP. These follow Claude's tool definition format and are used
by the proxy agent and triage pipeline.
"""

from typing import List, Dict, Any


# ──────────────────────────────────────────────
# Read-only tools (12)
# ──────────────────────────────────────────────

_READ_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "cipp_list_tenants",
        "description": (
            "List all Microsoft 365 tenants managed in CIPP. Returns tenant names, "
            "default domains, and customer IDs. Use this to find a tenant's domain "
            "when you don't already know it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "cipp_list_users",
        "description": (
            "List users in a Microsoft 365 tenant via CIPP. Returns user details "
            "including display name, UPN, email, licenses, sign-in status, and account "
            "enabled state. Use tenant_filter from the client's azure_tenant_domain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
    {
        "name": "cipp_list_groups",
        "description": (
            "List groups in a Microsoft 365 tenant via CIPP. Returns security groups, "
            "distribution lists, and Microsoft 365 groups with membership counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
    {
        "name": "cipp_list_user_groups",
        "description": (
            "List all groups a specific user belongs to in Microsoft 365 via CIPP. "
            "Use this to check a user's group memberships for troubleshooting access issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID (GUID or UPN like user@domain.com)",
                },
            },
            "required": ["tenant_filter", "user_id"],
        },
    },
    {
        "name": "cipp_list_mailboxes",
        "description": (
            "List mailboxes in a Microsoft 365 tenant via CIPP. Returns mailbox "
            "details including type (user, shared, room), size, and archive status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
    {
        "name": "cipp_list_mailbox_permissions",
        "description": (
            "List permissions on a specific mailbox in Microsoft 365 via CIPP. "
            "Shows who has Full Access, Send As, or Send on Behalf permissions. "
            "Useful for investigating mailbox access issues or security audits."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "user_id": {
                    "type": "string",
                    "description": "Mailbox owner User ID (GUID or UPN)",
                },
            },
            "required": ["tenant_filter", "user_id"],
        },
    },
    {
        "name": "cipp_list_mailbox_rules",
        "description": (
            "List inbox rules for a specific mailbox in Microsoft 365 via CIPP. "
            "Shows auto-forward rules, move rules, and delete rules. Critical for "
            "investigating compromised accounts (attackers often add forwarding rules)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID (GUID or UPN)",
                },
            },
            "required": ["tenant_filter", "user_id"],
        },
    },
    {
        "name": "cipp_list_devices",
        "description": (
            "List Intune managed devices in a Microsoft 365 tenant via CIPP. "
            "Returns device details including OS, compliance state, last sync time, "
            "and encryption status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
    {
        "name": "cipp_list_licenses",
        "description": (
            "List license assignments in a Microsoft 365 tenant via CIPP. "
            "Shows available vs consumed licenses for each SKU (Business Basic, "
            "Business Premium, E3, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
    {
        "name": "cipp_list_sign_ins",
        "description": (
            "List recent sign-in logs for a Microsoft 365 tenant via CIPP. "
            "Shows user sign-in activity including success/failure, location, "
            "device info, and conditional access results. Useful for security "
            "investigations and troubleshooting login issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
    {
        "name": "cipp_list_defender_state",
        "description": (
            "List Microsoft Defender status for devices in a Microsoft 365 tenant "
            "via CIPP. Shows Defender AV status, signature freshness, scan results, "
            "and any active threats detected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
    {
        "name": "cipp_list_conditional_access_policies",
        "description": (
            "List Conditional Access policies in a Microsoft 365 tenant via CIPP. "
            "Shows policy names, states (enabled/disabled/report-only), conditions, "
            "and grant/session controls. Useful for troubleshooting access issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
            },
            "required": ["tenant_filter"],
        },
    },
]


# ──────────────────────────────────────────────
# Write/action tools (4)
# ──────────────────────────────────────────────

_WRITE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "cipp_reset_password",
        "description": (
            "Reset a user's password in Microsoft 365 via CIPP. Generates a random "
            "temporary password that the user must change on next sign-in. "
            "Use this for password reset requests or as part of compromised account response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID (GUID or UPN like user@domain.com)",
                },
            },
            "required": ["tenant_filter", "user_id"],
        },
    },
    {
        "name": "cipp_disable_user",
        "description": (
            "Disable a user account in Microsoft 365 via CIPP. Blocks sign-in "
            "and revokes active sessions. Use this for offboarding or compromised "
            "account containment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID (GUID or UPN like user@domain.com)",
                },
            },
            "required": ["tenant_filter", "user_id"],
        },
    },
    {
        "name": "cipp_device_action",
        "description": (
            "Execute an action on an Intune managed device via CIPP. "
            "Available actions: syncDevice (force policy sync), rebootNow (restart), "
            "locateDevice (find device location), remoteLock (lock device), "
            "retireDevice (remove company data)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "device_id": {
                    "type": "string",
                    "description": "Intune device ID (GUID)",
                },
                "action": {
                    "type": "string",
                    "enum": [
                        "syncDevice", "rebootNow", "locateDevice",
                        "remoteLock", "retireDevice",
                    ],
                    "description": "Action to execute on the device",
                },
            },
            "required": ["tenant_filter", "device_id", "action"],
        },
    },
    {
        "name": "cipp_edit_mailbox_permissions",
        "description": (
            "Edit mailbox permissions in Microsoft 365 via CIPP. Add or remove "
            "Full Access, Send As, or Send on Behalf permissions for a mailbox. "
            "Pass a permissions object with keys: AccessUser (UPN of delegate), "
            "AccessRights (FullAccess), SendAs (true/false), SendOnBehalf (true/false)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "user_id": {
                    "type": "string",
                    "description": "Mailbox owner User ID (GUID or UPN)",
                },
                "permissions": {
                    "type": "object",
                    "description": (
                        "Permission configuration: {AccessUser, AccessRights, "
                        "SendAs, SendOnBehalf}"
                    ),
                },
            },
            "required": ["tenant_filter", "user_id", "permissions"],
        },
    },
    {
        "name": "cipp_offboard_user",
        "description": (
            "Offboard a user in Microsoft 365 via CIPP's Offboarding Wizard. "
            "Performs multiple offboarding actions in one call. Set boolean flags "
            "in the options object to enable each action. "
            "Boolean options: ConvertToShared (convert mailbox to shared), "
            "HideFromGAL (hide from Global Address List), DeleteUser (delete the account), "
            "DisableSignIn, ResetPass, RevokeSessions, RemoveGroups, RemoveLicenses, "
            "RemoveRules, RemoveMobile, RemoveMFADevices, removeCalendarInvites, "
            "removePermissions, ClearImmutableId, disableForwarding. "
            "Array options (each item is {\"value\": \"user@domain.com\"}): "
            "AccessAutomap (grant full mailbox access WITH automapping), "
            "AccessNoAutomap (grant full mailbox access WITHOUT automapping), "
            "OnedriveAccess (grant OneDrive access). "
            "String options: OOO (set out-of-office message). "
            "Object options: forward ({\"value\": \"user@domain.com\"} to set forwarding)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_filter": {
                    "type": "string",
                    "description": "Tenant domain (e.g., contoso.onmicrosoft.com)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User UPN to offboard (e.g., user@domain.com)",
                },
                "options": {
                    "type": "object",
                    "description": (
                        "Offboarding options. Example: "
                        "{\"ConvertToShared\": true, \"HideFromGAL\": true, "
                        "\"DeleteUser\": true, "
                        "\"AccessAutomap\": [{\"value\": \"delegate@domain.com\"}], "
                        "\"OnedriveAccess\": [{\"value\": \"delegate@domain.com\"}]}"
                    ),
                },
            },
            "required": ["tenant_filter", "user_id", "options"],
        },
    },
]


def get_cipp_tools() -> List[Dict[str, Any]]:
    """
    Get all CIPP tools (read + write) for the proxy agent.

    Returns:
        List of all 16 tool definitions in Claude format
    """
    return _READ_TOOLS + _WRITE_TOOLS


def get_cipp_read_tools() -> List[Dict[str, Any]]:
    """
    Get read-only CIPP tools for the triage pipeline.

    Returns:
        List of 12 read-only tool definitions in Claude format
    """
    return list(_READ_TOOLS)


def get_cipp_write_tools() -> List[Dict[str, Any]]:
    """
    Get write/action CIPP tools.

    Returns:
        List of 4 write tool definitions in Claude format
    """
    return list(_WRITE_TOOLS)
