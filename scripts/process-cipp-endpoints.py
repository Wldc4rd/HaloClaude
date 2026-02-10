"""
Process CIPP-API endpoint files into a comprehensive markdown reference.

Reads raw-endpoints.txt (list of .ps1 file paths from the CIPP-API repo)
and generates docs/CIPP/api-endpoints.md with all endpoints organized by category.
"""

import re
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

# Category descriptions for the doc header sections
CATEGORY_DESCRIPTIONS = {
    "CIPP/Core": "Internal CIPP platform operations, diagnostics, and Graph API proxying.",
    "CIPP/Extensions": "PSA/RMM extension integrations (Halo, ConnectWise, NinjaRMM, etc.).",
    "CIPP/Scheduler": "Scheduled task management.",
    "CIPP/Settings": "CIPP instance configuration, permissions, and administration.",
    "CIPP/Setup": "Initial CIPP setup and SAM (Secure Application Model) configuration.",
    "Email-Exchange/Administration": "Exchange Online mailbox management and operations.",
    "Email-Exchange/Administration/Contacts": "Exchange contacts management.",
    "Email-Exchange/Administration/Mailbox Retention": "Mailbox retention policy management.",
    "Email-Exchange/Reports": "Exchange security and configuration reports.",
    "Email-Exchange/Resources": "Room and equipment mailbox management.",
    "Email-Exchange/Spamfilter": "Anti-spam, quarantine, and protection policies.",
    "Email-Exchange/Tools": "Exchange diagnostic and utility tools.",
    "Email-Exchange/Transport": "Transport rules and Exchange connectors.",
    "Endpoint/Applications": "Intune application management.",
    "Endpoint/Autopilot": "Windows Autopilot device management.",
    "Endpoint/MEM": "Microsoft Endpoint Manager (Intune) device management, policies, and security.",
    "Endpoint/Reports": "Intune device reports.",
    "Identity": "Identity-level operations.",
    "Identity/Administration/Devices": "Azure AD device management.",
    "Identity/Administration/Groups": "Group management.",
    "Identity/Administration/Users": "User lifecycle management, security actions, and user data queries.",
    "Identity/Reports": "Identity security and status reports.",
    "Security": "Microsoft 365 Defender alerts and incidents.",
    "Security/Safe-Links-Policy": "Safe Links policy management.",
    "Teams-Sharepoint": "Microsoft Teams and SharePoint Online management.",
    "Tenant/Administration": "Tenant-level administration operations.",
    "Tenant/Administration/Alerts": "Audit log and webhook alert management.",
    "Tenant/Administration/Application Approval": "Enterprise application and consent management.",
    "Tenant/Administration/Domains": "Domain management.",
    "Tenant/Administration/Tenant": "Tenant record management within CIPP.",
    "Tenant/Conditional": "Conditional Access policy management.",
    "Tenant/GDAP": "Granular Delegated Admin Privileges management.",
    "Tenant/Reports": "Tenant-level reports.",
    "Tenant/Standards": "Standards compliance, Best Practice Analyzer, and domain health.",
    "Tenant/Tools": "Tenant tools and utilities.",
    "Tools/GitHub": "Community repository and release management.",
    "Root": "Built-in test framework and utilities.",
}


def infer_method(endpoint_name: str) -> str:
    """Infer HTTP method from endpoint name prefix."""
    lower = endpoint_name.lower()
    if lower.startswith(("list", "get")):
        return "GET"
    # Special cases for BPA/Domain analyzer list endpoints
    if "analyser_list" in lower or "bestpractice" in lower:
        return "GET"
    return "POST"


def parse_endpoints(raw_file: Path) -> dict:
    """Parse raw endpoint file paths into categorized endpoint dict."""
    endpoints = defaultdict(list)

    with open(raw_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            match = re.search(r"HTTP Functions/(.+)$", line)
            if not match:
                continue

            rel_path = match.group(1)
            parts = rel_path.split("/")
            filename = parts[-1]
            category = "/".join(parts[:-1]) if len(parts) > 1 else "Root"

            # Extract endpoint name: Invoke-XxxYyy.ps1 -> XxxYyy
            name_match = re.search(r"Invoke-(.+?)\.ps1$", filename, re.IGNORECASE)
            if not name_match:
                name_match = re.search(r"(.+?)\.ps1$", filename, re.IGNORECASE)

            if name_match:
                ep_name = name_match.group(1)
                endpoints[category].append(ep_name)

    return dict(endpoints)


def generate_markdown(endpoints: dict) -> str:
    """Generate the full markdown document."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = sum(len(eps) for eps in endpoints.values())

    lines = [
        "# CIPP API Endpoint Reference",
        "",
        f"Complete reference for all CIPP (CyberDrain Improved Partner Portal) API endpoints.",
        f"Auto-generated from [CIPP-API GitHub](https://github.com/KelvinTegelaar/CIPP-API) on {now}.",
        f"Total: **{total} endpoints**.",
        "",
        "## Authentication",
        "",
        "OAuth2 Client Credentials via Azure AD:",
        "- **Token URL:** `https://login.microsoftonline.com/{TenantId}/oauth2/v2.0/token`",
        "- **Scope:** `api://{ApplicationId}/.default`",
        "- **Grant Type:** `client_credentials`",
        "- **Auth Header:** `Authorization: Bearer {token}`",
        "",
        "## Common Parameters",
        "",
        "Most tenant-scoped endpoints require:",
        "- `TenantFilter` (string): Tenant domain (e.g., `contoso.onmicrosoft.com`).",
        "",
        "For POST endpoints, parameters are sent as JSON body. For GET endpoints, parameters are query strings.",
        "",
        "## Endpoint Naming Conventions",
        "",
        "| Prefix | HTTP Method | Purpose |",
        "|--------|------------|---------|",
        "| `List*` / `Get*` | GET | Read/query data |",
        "| `Exec*` | POST | Execute an action or complex operation |",
        "| `Add*` | POST | Create a new resource |",
        "| `Edit*` | POST | Modify an existing resource |",
        "| `Remove*` / `Delete*` | POST | Delete a resource |",
        "| `Deploy*` | POST | Deploy a template/config to tenants |",
        "| `Set*` | POST | Set/update a configuration |",
        "",
        "---",
        "",
    ]

    for category in sorted(endpoints.keys()):
        eps = sorted(endpoints[category])
        desc = CATEGORY_DESCRIPTIONS.get(category, "")

        lines.append(f"## {category} ({len(eps)} endpoints)")
        lines.append("")
        if desc:
            lines.append(desc)
            lines.append("")

        lines.append("| Method | Endpoint | Description |")
        lines.append("|--------|----------|-------------|")

        for ep in eps:
            method = infer_method(ep)
            lines.append(f"| {method} | `api/{ep}` | |")

        lines.append("")

    # Add HaloClaude integration section
    lines.extend([
        "---",
        "",
        "## HaloClaude Integration",
        "",
        "Of these endpoints, HaloClaude currently integrates **17 tools** (12 read-only + 5 write).",
        "See `cipp/tools.py` for the full tool definitions.",
        "",
        "### Read-only (proxy + MCP + triage)",
        "| CIPP Endpoint | HaloClaude Tool |",
        "|--------------|----------------|",
        "| `api/ListTenants` | `cipp_list_tenants` |",
        "| `api/ListUsers` | `cipp_list_users` |",
        "| `api/ListGroups` | `cipp_list_groups` |",
        "| `api/ListUserGroups` | `cipp_list_user_groups` |",
        "| `api/ListMailboxes` | `cipp_list_mailboxes` |",
        "| `api/ListmailboxPermissions` | `cipp_list_mailbox_permissions` |",
        "| `api/ListMailboxRules` | `cipp_list_mailbox_rules` |",
        "| `api/ListDevices` | `cipp_list_devices` |",
        "| `api/ListLicenses` | `cipp_list_licenses` |",
        "| `api/ListSignIns` | `cipp_list_sign_ins` |",
        "| `api/ListDefenderState` | `cipp_list_defender_state` |",
        "| `api/ListConditionalAccessPolicies` | `cipp_list_conditional_access_policies` |",
        "",
        "### Write/action (proxy + MCP only, NOT triage)",
        "| CIPP Endpoint | HaloClaude Tool |",
        "|--------------|----------------|",
        "| `api/ExecResetPass` | `cipp_reset_password` |",
        "| `api/ExecDisableUser` | `cipp_disable_user` |",
        "| `api/ExecDeviceAction` | `cipp_device_action` |",
        "| `api/ExecEditMailboxPermissions` | `cipp_edit_mailbox_permissions` |",
        "| `api/ExecOffboardUser` | `cipp_offboard_user` |",
        "",
    ])

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: process-cipp-endpoints.py <docs-dir>")
        sys.exit(1)

    docs_dir = Path(sys.argv[1])
    raw_file = docs_dir / "raw-endpoints.txt"

    if not raw_file.exists():
        print(f"Error: {raw_file} not found. Run refresh-cipp-docs.sh first.")
        sys.exit(1)

    endpoints = parse_endpoints(raw_file)
    total = sum(len(eps) for eps in endpoints.values())
    print(f"Parsed {total} endpoints across {len(endpoints)} categories")

    markdown = generate_markdown(endpoints)

    output_file = docs_dir / "api-endpoints.md"
    output_file.write_text(markdown, encoding="utf-8")
    print(f"Generated {output_file}")


if __name__ == "__main__":
    main()
