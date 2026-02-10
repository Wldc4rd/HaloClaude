"""
CIPP (CyberDrain Improved Partner Portal) API Client

Provides methods to interact with the CIPP API for Microsoft 365
multi-tenant management including users, groups, devices, mailboxes,
licenses, and security features.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from .auth import CippAuthManager

logger = logging.getLogger(__name__)


class CippClient:
    """Client for CIPP REST API."""

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        application_id: Optional[str] = None,
    ):
        """
        Initialize the CIPP client.

        Args:
            base_url: CIPP API URL (e.g., https://your-cipp.azurewebsites.net)
            tenant_id: Azure AD tenant ID for authentication
            client_id: OAuth client ID
            client_secret: OAuth client secret
            application_id: CIPP application ID for scope (defaults to client_id)
        """
        self.base_url = base_url.rstrip("/")

        self._auth = CippAuthManager(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            application_id=application_id,
        )
        self._http_client: Optional[httpx.AsyncClient] = None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def close(self):
        """Close HTTP client and auth manager."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        await self._auth.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Make an authenticated request to CIPP API.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "api/ListTenants")
            params: Query parameters
            json_body: JSON body for POST requests

        Returns:
            Response JSON
        """
        token = await self._auth.get_token()
        client = await self.get_http_client()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        kwargs: Dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        }
        if params:
            kwargs["params"] = params
        if json_body:
            kwargs["json"] = json_body
            kwargs["headers"]["Content-Type"] = "application/json"

        response = await client.request(**kwargs)

        if response.status_code >= 400:
            body = response.text
            logger.error(
                f"CIPP API error: {response.status_code} {method} "
                f"{endpoint} - {body[:500]}"
            )

        response.raise_for_status()
        return response.json()

    # ──────────────────────────────────────────────
    # Read-only endpoints
    # ──────────────────────────────────────────────

    async def list_tenants(self) -> List[Dict[str, Any]]:
        """
        List all tenants managed in CIPP.

        Returns:
            List of tenant objects with customerId, defaultDomainName, displayName
        """
        logger.debug("Fetching CIPP tenant list")
        return await self._request("GET", "api/ListTenants")

    async def list_users(self, tenant_filter: str) -> List[Dict[str, Any]]:
        """
        List users in a tenant.

        Args:
            tenant_filter: Tenant domain (e.g., contoso.onmicrosoft.com)

        Returns:
            List of user objects
        """
        logger.debug(f"Fetching CIPP users for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListUsers",
            params={"TenantFilter": tenant_filter},
        )

    async def list_groups(self, tenant_filter: str) -> List[Dict[str, Any]]:
        """
        List groups in a tenant.

        Args:
            tenant_filter: Tenant domain

        Returns:
            List of group objects
        """
        logger.debug(f"Fetching CIPP groups for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListGroups",
            params={"TenantFilter": tenant_filter},
        )

    async def list_user_groups(
        self, tenant_filter: str, user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        List groups a specific user belongs to.

        Args:
            tenant_filter: Tenant domain
            user_id: User ID (GUID or UPN)

        Returns:
            List of group memberships
        """
        logger.debug(f"Fetching CIPP groups for user {user_id} in {tenant_filter}")
        return await self._request(
            "GET", "api/ListUserGroups",
            params={"TenantFilter": tenant_filter, "userId": user_id},
        )

    async def list_mailboxes(self, tenant_filter: str) -> List[Dict[str, Any]]:
        """
        List mailboxes in a tenant.

        Args:
            tenant_filter: Tenant domain

        Returns:
            List of mailbox objects
        """
        logger.debug(f"Fetching CIPP mailboxes for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListMailboxes",
            params={"TenantFilter": tenant_filter},
        )

    async def list_mailbox_permissions(
        self, tenant_filter: str, user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        List permissions on a specific mailbox.

        Args:
            tenant_filter: Tenant domain
            user_id: User ID (GUID or UPN) of the mailbox owner

        Returns:
            List of mailbox permissions
        """
        logger.debug(f"Fetching CIPP mailbox permissions for {user_id} in {tenant_filter}")
        return await self._request(
            "GET", "api/ListMailboxPermissions",
            params={"TenantFilter": tenant_filter, "userId": user_id},
        )

    async def list_mailbox_rules(
        self, tenant_filter: str, user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        List inbox rules for a specific mailbox.

        Args:
            tenant_filter: Tenant domain
            user_id: User ID (GUID or UPN)

        Returns:
            List of inbox rules
        """
        logger.debug(f"Fetching CIPP mailbox rules for {user_id} in {tenant_filter}")
        return await self._request(
            "GET", "api/ListMailboxRules",
            params={"TenantFilter": tenant_filter, "userId": user_id},
        )

    async def list_devices(self, tenant_filter: str) -> List[Dict[str, Any]]:
        """
        List devices (Intune managed) in a tenant.

        Args:
            tenant_filter: Tenant domain

        Returns:
            List of device objects
        """
        logger.debug(f"Fetching CIPP devices for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListDevices",
            params={"TenantFilter": tenant_filter},
        )

    async def list_licenses(self, tenant_filter: str) -> List[Dict[str, Any]]:
        """
        List license assignments in a tenant.

        Args:
            tenant_filter: Tenant domain

        Returns:
            List of license objects with counts and assignments
        """
        logger.debug(f"Fetching CIPP licenses for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListLicenses",
            params={"TenantFilter": tenant_filter},
        )

    async def list_sign_ins(self, tenant_filter: str) -> List[Dict[str, Any]]:
        """
        List recent sign-in logs for a tenant.

        Args:
            tenant_filter: Tenant domain

        Returns:
            List of sign-in log entries
        """
        logger.debug(f"Fetching CIPP sign-in logs for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListSignIns",
            params={"TenantFilter": tenant_filter},
        )

    async def list_defender_state(self, tenant_filter: str) -> List[Dict[str, Any]]:
        """
        List Microsoft Defender status for devices in a tenant.

        Args:
            tenant_filter: Tenant domain

        Returns:
            List of Defender state objects per device
        """
        logger.debug(f"Fetching CIPP Defender state for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListDefenderState",
            params={"TenantFilter": tenant_filter},
        )

    async def list_conditional_access_policies(
        self, tenant_filter: str,
    ) -> List[Dict[str, Any]]:
        """
        List Conditional Access policies in a tenant.

        Args:
            tenant_filter: Tenant domain

        Returns:
            List of Conditional Access policy objects
        """
        logger.debug(f"Fetching CIPP CA policies for tenant {tenant_filter}")
        return await self._request(
            "GET", "api/ListConditionalAccessPolicies",
            params={"TenantFilter": tenant_filter},
        )

    # ──────────────────────────────────────────────
    # Write/action endpoints
    # ──────────────────────────────────────────────

    async def reset_password(
        self, tenant_filter: str, user_id: str,
    ) -> Dict[str, Any]:
        """
        Reset a user's password (generates a random password).

        Args:
            tenant_filter: Tenant domain
            user_id: User ID (GUID or UPN)

        Returns:
            Result with new temporary password
        """
        logger.info(f"CIPP: Resetting password for {user_id} in {tenant_filter}")
        return await self._request(
            "POST", "api/ExecResetPass",
            json_body={"TenantFilter": tenant_filter, "userId": user_id},
        )

    async def disable_user(
        self, tenant_filter: str, user_id: str,
    ) -> Dict[str, Any]:
        """
        Disable a user account.

        Args:
            tenant_filter: Tenant domain
            user_id: User ID (GUID or UPN)

        Returns:
            Result confirming user was disabled
        """
        logger.info(f"CIPP: Disabling user {user_id} in {tenant_filter}")
        return await self._request(
            "POST", "api/ExecDisableUser",
            json_body={"TenantFilter": tenant_filter, "userId": user_id},
        )

    async def device_action(
        self,
        tenant_filter: str,
        device_id: str,
        action: str,
    ) -> Dict[str, Any]:
        """
        Execute an action on an Intune managed device.

        Args:
            tenant_filter: Tenant domain
            device_id: Intune device ID
            action: Action to execute (syncDevice, rebootNow, locateDevice, remoteLock, retireDevice)

        Returns:
            Result of the device action
        """
        logger.info(f"CIPP: Device action '{action}' on {device_id} in {tenant_filter}")
        return await self._request(
            "POST", "api/ExecDeviceAction",
            json_body={
                "TenantFilter": tenant_filter,
                "GUID": device_id,
                "Action": action,
            },
        )

    async def edit_mailbox_permissions(
        self,
        tenant_filter: str,
        user_id: str,
        permissions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Edit mailbox permissions (add/remove delegates).

        Args:
            tenant_filter: Tenant domain
            user_id: User ID (GUID or UPN) of the mailbox owner
            permissions: Permission configuration dict with keys like
                         AccessUser, AccessRights, SendAs, SendOnBehalf

        Returns:
            Result confirming permission changes
        """
        logger.info(f"CIPP: Editing mailbox permissions for {user_id} in {tenant_filter}")
        body = {"TenantFilter": tenant_filter, "userId": user_id}
        body.update(permissions)
        return await self._request(
            "POST", "api/ExecEditMailboxPermissions",
            json_body=body,
        )
