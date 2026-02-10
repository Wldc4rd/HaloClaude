# CIPP API Endpoint Reference

Complete reference for all CIPP (CyberDrain Improved Partner Portal) API endpoints.
Auto-generated from [CIPP-API GitHub](https://github.com/KelvinTegelaar/CIPP-API) on 2026-02-10.
Total: **436 endpoints**.

## Authentication

OAuth2 Client Credentials via Azure AD:
- **Token URL:** `https://login.microsoftonline.com/{TenantId}/oauth2/v2.0/token`
- **Scope:** `api://{ApplicationId}/.default`
- **Grant Type:** `client_credentials`
- **Auth Header:** `Authorization: Bearer {token}`

## Common Parameters

Most tenant-scoped endpoints require:
- `TenantFilter` (string): Tenant domain (e.g., `contoso.onmicrosoft.com`).

For POST endpoints, parameters are sent as JSON body. For GET endpoints, parameters are query strings.

## Endpoint Naming Conventions

| Prefix | HTTP Method | Purpose |
|--------|------------|---------|
| `List*` / `Get*` | GET | Read/query data |
| `Exec*` | POST | Execute an action or complex operation |
| `Add*` | POST | Create a new resource |
| `Edit*` | POST | Modify an existing resource |
| `Remove*` / `Delete*` | POST | Delete a resource |
| `Deploy*` | POST | Deploy a template/config to tenants |
| `Set*` | POST | Set/update a configuration |

---

## CIPP/Core (28 endpoints)

Internal CIPP platform operations, diagnostics, and Graph API proxying.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecAddAlert` | |
| POST | `api/ExecAppInsightsQuery` | |
| POST | `api/ExecAzBobbyTables` | |
| POST | `api/ExecCIPPDBCache` | |
| POST | `api/ExecCPVRefresh` | |
| POST | `api/ExecCippFunction` | |
| POST | `api/ExecCloneTemplate` | |
| POST | `api/ExecDiagnosticsPresets` | |
| POST | `api/ExecDurableFunctions` | |
| POST | `api/ExecEditTemplate` | |
| POST | `api/ExecGeoIPLookup` | |
| POST | `api/ExecListBackup` | |
| POST | `api/ExecPartnerWebhook` | |
| POST | `api/ExecServicePrincipals` | |
| POST | `api/ExecSetCIPPAutoBackup` | |
| POST | `api/ExecSetPackageTag` | |
| GET | `api/GetCippAlerts` | |
| GET | `api/GetVersion` | |
| GET | `api/ListAdminPortalLicenses` | |
| GET | `api/ListApiTest` | |
| GET | `api/ListCustomDataMappings` | |
| GET | `api/ListDiagnosticsPresets` | |
| GET | `api/ListDirectoryObjects` | |
| GET | `api/ListEmptyResults` | |
| GET | `api/ListExtensionCacheData` | |
| GET | `api/ListGraphBulkRequest` | |
| GET | `api/ListGraphRequest` | |
| POST | `api/PublicPing` | |

## CIPP/Extensions (5 endpoints)

PSA/RMM extension integrations (Halo, ConnectWise, NinjaRMM, etc.).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecExtensionMapping` | |
| POST | `api/ExecExtensionSync` | |
| POST | `api/ExecExtensionTest` | |
| POST | `api/ExecExtensionsConfig` | |
| GET | `api/ListExtensionSync` | |

## CIPP/Scheduler (4 endpoints)

Scheduled task management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddScheduledItem` | |
| GET | `api/ListScheduledItemDetails` | |
| GET | `api/ListScheduledItems` | |
| POST | `api/RemoveScheduledItem` | |

## CIPP/Settings (36 endpoints)

CIPP instance configuration, permissions, and administration.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecAPIPermissionList` | |
| POST | `api/ExecAccessChecks` | |
| POST | `api/ExecAddTrustedIP` | |
| POST | `api/ExecApiClient` | |
| POST | `api/ExecBackendURLs` | |
| POST | `api/ExecBackupRetentionConfig` | |
| POST | `api/ExecBrandingSettings` | |
| POST | `api/ExecCPVPermissions` | |
| POST | `api/ExecCippReplacemap` | |
| POST | `api/ExecCreateDefaultGroups` | |
| POST | `api/ExecCustomData` | |
| POST | `api/ExecCustomRole` | |
| POST | `api/ExecDnsConfig` | |
| POST | `api/ExecExchangeRoleRepair` | |
| POST | `api/ExecExcludeLicenses` | |
| POST | `api/ExecExcludeTenant` | |
| POST | `api/ExecJITAdminSettings` | |
| POST | `api/ExecMaintenanceScripts` | |
| POST | `api/ExecNotificationConfig` | |
| POST | `api/ExecOffloadFunctions` | |
| POST | `api/ExecPartnerMode` | |
| POST | `api/ExecPasswordConfig` | |
| POST | `api/ExecPermissionRepair` | |
| POST | `api/ExecRemoveTenant` | |
| POST | `api/ExecRestoreBackup` | |
| POST | `api/ExecRunBackup` | |
| POST | `api/ExecRunTenantGroupRule` | |
| POST | `api/ExecSAMAppPermissions` | |
| POST | `api/ExecSAMRoles` | |
| POST | `api/ExecTenantGroup` | |
| POST | `api/ExecTimeSettings` | |
| POST | `api/ExecWebhookSubscriptions` | |
| GET | `api/ListCustomRole` | |
| GET | `api/ListCustomVariables` | |
| GET | `api/ListExcludedLicenses` | |
| GET | `api/ListTenantGroups` | |

## CIPP/Setup (7 endpoints)

Initial CIPP setup and SAM (Secure Application Model) configuration.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecAddTenant` | |
| POST | `api/ExecCombinedSetup` | |
| POST | `api/ExecCreateSAMApp` | |
| POST | `api/ExecDeviceCodeLogon` | |
| POST | `api/ExecSAMSetup` | |
| POST | `api/ExecTokenExchange` | |
| POST | `api/ExecUpdateRefreshToken` | |

## Email-Exchange/Administration (38 endpoints)

Exchange Online mailbox management and operations.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddSharedMailbox` | |
| POST | `api/ExecConvertMailbox` | |
| POST | `api/ExecCopyForSent` | |
| POST | `api/ExecEditCalendarPermissions` | |
| POST | `api/ExecEditMailboxPermissions` | |
| POST | `api/ExecEmailForward` | |
| POST | `api/ExecEnableArchive` | |
| POST | `api/ExecEnableAutoExpandingArchive` | |
| POST | `api/ExecGroupsDelete` | |
| POST | `api/ExecGroupsDeliveryManagement` | |
| POST | `api/ExecGroupsHideFromGAL` | |
| POST | `api/ExecHVEUser` | |
| POST | `api/ExecHideFromGAL` | |
| POST | `api/ExecMailboxMobileDevices` | |
| POST | `api/ExecModifyCalPerms` | |
| POST | `api/ExecModifyContactPerms` | |
| POST | `api/ExecModifyMBPerms` | |
| POST | `api/ExecRemoveMailboxRule` | |
| POST | `api/ExecRemoveRestrictedUser` | |
| POST | `api/ExecSetCalendarProcessing` | |
| POST | `api/ExecSetLitigationHold` | |
| POST | `api/ExecSetMailboxEmailSize` | |
| POST | `api/ExecSetMailboxLocale` | |
| POST | `api/ExecSetMailboxQuota` | |
| POST | `api/ExecSetMailboxRule` | |
| POST | `api/ExecSetOoO` | |
| POST | `api/ExecSetRecipientLimits` | |
| POST | `api/ExecSetRetentionHold` | |
| POST | `api/ExecStartManagedFolderAssistant` | |
| GET | `api/ListCalendarPermissions` | |
| GET | `api/ListContactPermissions` | |
| GET | `api/ListMailboxMobileDevices` | |
| GET | `api/ListMailboxRules` | |
| GET | `api/ListMailboxes` | |
| GET | `api/ListOoO` | |
| GET | `api/ListRestrictedUsers` | |
| GET | `api/ListSharedMailboxStatistics` | |
| GET | `api/ListmailboxPermissions` | |

## Email-Exchange/Administration/Contacts (9 endpoints)

Exchange contacts management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddContact` | |
| POST | `api/AddContactTemplates` | |
| POST | `api/DeployContactTemplates` | |
| POST | `api/EditContact` | |
| POST | `api/EditContactTemplates` | |
| GET | `api/ListContactTemplates` | |
| GET | `api/ListContacts` | |
| POST | `api/RemoveContact` | |
| POST | `api/RemoveContactTemplates` | |

## Email-Exchange/Administration/Mailbox Retention (3 endpoints)

Mailbox retention policy management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecManageRetentionPolicies` | |
| POST | `api/ExecManageRetentionTags` | |
| POST | `api/ExecSetMailboxRetentionPolicies` | |

## Email-Exchange/Reports (6 endpoints)

Exchange security and configuration reports.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `api/ListAntiPhishingFilters` | |
| GET | `api/ListGlobalAddressList` | |
| GET | `api/ListMailboxCAS` | |
| GET | `api/ListMalwareFilters` | |
| GET | `api/ListSafeAttachmentsFilters` | |
| GET | `api/ListSharedMailboxAccountEnabled` | |

## Email-Exchange/Resources (9 endpoints)

Room and equipment mailbox management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddEquipmentMailbox` | |
| POST | `api/AddRoomList` | |
| POST | `api/AddRoomMailbox` | |
| POST | `api/EditEquipmentMailbox` | |
| POST | `api/EditRoomList` | |
| POST | `api/EditRoomMailbox` | |
| GET | `api/ListEquipment` | |
| GET | `api/ListRoomLists` | |
| GET | `api/ListRooms` | |

## Email-Exchange/Spamfilter (21 endpoints)

Anti-spam, quarantine, and protection policies.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddQuarantinePolicy` | |
| POST | `api/AddSpamFilter` | |
| POST | `api/AddSpamFilterTemplate` | |
| POST | `api/AddTenantAllowBlockList` | |
| POST | `api/EditAntiPhishingFilter` | |
| POST | `api/EditMalwareFilter` | |
| POST | `api/EditQuarantinePolicy` | |
| POST | `api/EditSafeAttachmentsFilter` | |
| POST | `api/EditSpamFilter` | |
| POST | `api/ExecQuarantineManagement` | |
| GET | `api/ListConnectionFilter` | |
| GET | `api/ListConnectionFilterTemplates` | |
| GET | `api/ListMailQuarantine` | |
| GET | `api/ListMailQuarantineMessage` | |
| GET | `api/ListQuarantinePolicy` | |
| GET | `api/ListSpamFilterTemplates` | |
| GET | `api/ListSpamfilter` | |
| POST | `api/RemoveConnectionfilterTemplate` | |
| POST | `api/RemoveQuarantinePolicy` | |
| POST | `api/RemoveSpamfilter` | |
| POST | `api/RemoveSpamfilterTemplate` | |

## Email-Exchange/Tools (5 endpoints)

Exchange diagnostic and utility tools.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecMailTest` | |
| POST | `api/ExecMailboxRestore` | |
| GET | `api/ListExoRequest` | |
| GET | `api/ListMailboxRestores` | |
| GET | `api/ListMessageTrace` | |

## Email-Exchange/Transport (17 endpoints)

Transport rules and Exchange connectors.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddConnectionFilter` | |
| POST | `api/AddConnectionFilterTemplate` | |
| POST | `api/AddEditTransportRule` | |
| POST | `api/AddExConnector` | |
| POST | `api/AddExConnectorTemplate` | |
| POST | `api/AddTransportRule` | |
| POST | `api/AddTransportTemplate` | |
| POST | `api/EditExConnector` | |
| POST | `api/EditTransportRule` | |
| GET | `api/ListExConnectorTemplates` | |
| GET | `api/ListExchangeConnectors` | |
| GET | `api/ListTransportRules` | |
| GET | `api/ListTransportRulesTemplates` | |
| POST | `api/RemoveExConnector` | |
| POST | `api/RemoveExConnectorTemplate` | |
| POST | `api/RemoveTransportRule` | |
| POST | `api/RemoveTransportRuleTemplate` | |

## Endpoint/Applications (12 endpoints)

Intune application management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddChocoApp` | |
| POST | `api/AddMSPApp` | |
| POST | `api/AddOfficeApp` | |
| POST | `api/AddStoreApp` | |
| POST | `api/ExecAppUpload` | |
| POST | `api/ExecAssignApp` | |
| POST | `api/ExecSyncVPP` | |
| GET | `api/ListApplicationQueue` | |
| GET | `api/ListApps` | |
| GET | `api/ListAppsRepository` | |
| POST | `api/RemoveApp` | |
| POST | `api/RemoveQueuedApp` | |

## Endpoint/Autopilot (11 endpoints)

Windows Autopilot device management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddAPDevice` | |
| POST | `api/AddAutopilotConfig` | |
| POST | `api/AddEnrollment` | |
| POST | `api/ExecAssignAPDevice` | |
| POST | `api/ExecRenameAPDevice` | |
| POST | `api/ExecSetAPDeviceGroupTag` | |
| POST | `api/ExecSyncAPDevices` | |
| GET | `api/ListAPDevices` | |
| GET | `api/ListAutopilotconfig` | |
| POST | `api/RemoveAPDevice` | |
| POST | `api/RemoveAutopilotConfig` | |

## Endpoint/MEM (28 endpoints)

Microsoft Endpoint Manager (Intune) device management, policies, and security.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddAssignmentFilter` | |
| POST | `api/AddAssignmentFilterTemplate` | |
| POST | `api/AddDefenderDeployment` | |
| POST | `api/AddIntuneTemplate` | |
| POST | `api/AddPolicy` | |
| POST | `api/EditAssignmentFilter` | |
| POST | `api/EditIntunePolicy` | |
| POST | `api/EditIntuneScript` | |
| POST | `api/EditPolicy` | |
| POST | `api/ExecAssignPolicy` | |
| POST | `api/ExecAssignmentFilter` | |
| POST | `api/ExecDeviceAction` | |
| POST | `api/ExecDevicePasscodeAction` | |
| POST | `api/ExecGetLocalAdminPassword` | |
| POST | `api/ExecGetRecoveryKey` | |
| GET | `api/ListAppProtectionPolicies` | |
| GET | `api/ListAssignmentFilterTemplates` | |
| GET | `api/ListAssignmentFilters` | |
| GET | `api/ListCompliancePolicies` | |
| GET | `api/ListDefenderState` | |
| GET | `api/ListDefenderTVM` | |
| GET | `api/ListIntunePolicy` | |
| GET | `api/ListIntuneScript` | |
| GET | `api/ListIntuneTemplates` | |
| POST | `api/RemoveAssignmentFilterTemplate` | |
| POST | `api/RemoveIntuneScript` | |
| POST | `api/RemoveIntuneTemplate` | |
| POST | `api/RemovePolicy` | |

## Endpoint/Reports (1 endpoints)

Intune device reports.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `api/ListDevices` | |

## Identity (1 endpoints)

Identity-level operations.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecSetCloudManaged` | |

## Identity/Administration/Devices (1 endpoints)

Azure AD device management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecDeviceDelete` | |

## Identity/Administration/Groups (8 endpoints)

Group management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddGroup` | |
| POST | `api/AddGroupTeam` | |
| POST | `api/AddGroupTemplate` | |
| POST | `api/EditGroup` | |
| GET | `api/ListGroupSenderAuthentication` | |
| GET | `api/ListGroupTemplates` | |
| GET | `api/ListGroups` | |
| POST | `api/RemoveGroupTemplate` | |

## Identity/Administration/Users (51 endpoints)

User lifecycle management, security actions, and user data queries.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddGuest` | |
| POST | `api/AddJITAdminTemplate` | |
| POST | `api/AddUser` | |
| POST | `api/AddUserBulk` | |
| POST | `api/AddUserDefaults` | |
| POST | `api/CIPPOffboardingJob` | |
| POST | `api/EditJITAdminTemplate` | |
| POST | `api/EditUser` | |
| POST | `api/EditUserAliases` | |
| POST | `api/ExecBECCheck` | |
| POST | `api/ExecBECRemediate` | |
| POST | `api/ExecBulkLicense` | |
| POST | `api/ExecClrImmId` | |
| POST | `api/ExecCreateTAP` | |
| POST | `api/ExecDisableUser` | |
| POST | `api/ExecDismissRiskyUser` | |
| POST | `api/ExecJITAdmin` | |
| POST | `api/ExecOffboardUser` | |
| POST | `api/ExecOneDriveShortCut` | |
| POST | `api/ExecOnedriveProvision` | |
| POST | `api/ExecPasswordNeverExpires` | |
| POST | `api/ExecPerUserMFA` | |
| POST | `api/ExecReprocessUserLicenses` | |
| POST | `api/ExecResetMFA` | |
| POST | `api/ExecResetPass` | |
| POST | `api/ExecRestoreDeleted` | |
| POST | `api/ExecRevokeSessions` | |
| POST | `api/ExecSendPush` | |
| POST | `api/ExecSetUserPhoto` | |
| GET | `api/ListDeletedItems` | |
| GET | `api/ListJITAdmin` | |
| GET | `api/ListJITAdminTemplates` | |
| GET | `api/ListNewUserDefaults` | |
| GET | `api/ListPerUserMFA` | |
| GET | `api/ListUserConditionalAccessPolicies` | |
| GET | `api/ListUserCounts` | |
| GET | `api/ListUserDevices` | |
| GET | `api/ListUserGroups` | |
| GET | `api/ListUserMailboxDetails` | |
| GET | `api/ListUserMailboxRules` | |
| GET | `api/ListUserPhoto` | |
| GET | `api/ListUserSettings` | |
| GET | `api/ListUserSigninLogs` | |
| GET | `api/ListUserTrustedBlockedSenders` | |
| GET | `api/ListUsers` | |
| POST | `api/PatchUser` | |
| POST | `api/RemoveDeletedObject` | |
| POST | `api/RemoveJITAdminTemplate` | |
| POST | `api/RemoveTrustedBlockedSender` | |
| POST | `api/RemoveUser` | |
| POST | `api/RemoveUserDefaultTemplate` | |

## Identity/Reports (5 endpoints)

Identity security and status reports.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `api/ListAzureADConnectStatus` | |
| GET | `api/ListBasicAuth` | |
| GET | `api/ListInactiveAccounts` | |
| GET | `api/ListMFAUsers` | |
| GET | `api/ListSignIns` | |

## Root (7 endpoints)

Built-in test framework and utilities.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddTestReport` | |
| POST | `api/DeleteTestReport` | |
| POST | `api/ExecTestRun` | |
| GET | `api/ListAvailableTests` | |
| GET | `api/ListTestReports` | |
| GET | `api/ListTests` | |
| POST | `api/New-CippCoreRequest` | |

## Security (6 endpoints)

Microsoft 365 Defender alerts and incidents.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecAlertsList` | |
| POST | `api/ExecIncidentsList` | |
| POST | `api/ExecMdoAlertsList` | |
| POST | `api/ExecSetMdoAlert` | |
| POST | `api/ExecSetSecurityAlert` | |
| POST | `api/ExecSetSecurityIncident` | |

## Security/Safe-Links-Policy (12 endpoints)

Safe Links policy management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddSafeLinksPolicyFromTemplate` | |
| POST | `api/AddSafeLinksPolicyTemplate` | |
| POST | `api/CreateSafeLinksPolicyTemplate` | |
| POST | `api/EditSafeLinksPolicy` | |
| POST | `api/EditSafeLinksPolicyTemplate` | |
| POST | `api/ExecDeleteSafeLinksPolicy` | |
| POST | `api/ExecNewSafeLinksPolicy` | |
| GET | `api/ListSafeLinksPolicy` | |
| GET | `api/ListSafeLinksPolicyDetails` | |
| GET | `api/ListSafeLinksPolicyTemplateDetails` | |
| GET | `api/ListSafeLinksPolicyTemplates` | |
| POST | `api/RemoveSafeLinksPolicyTemplate` | |

## Teams-Sharepoint (16 endpoints)

Microsoft Teams and SharePoint Online management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddSite` | |
| POST | `api/AddSiteBulk` | |
| POST | `api/AddTeam` | |
| POST | `api/DeleteSharepointSite` | |
| POST | `api/ExecRemoveTeamsVoicePhoneNumberAssignment` | |
| POST | `api/ExecSetSharePointMember` | |
| POST | `api/ExecSharePointPerms` | |
| POST | `api/ExecTeamsVoicePhoneNumberAssignment` | |
| GET | `api/ListSharepointAdminUrl` | |
| GET | `api/ListSharepointQuota` | |
| GET | `api/ListSharepointSettings` | |
| GET | `api/ListSites` | |
| GET | `api/ListTeams` | |
| GET | `api/ListTeamsActivity` | |
| GET | `api/ListTeamsLisLocation` | |
| GET | `api/ListTeamsVoice` | |

## Tenant/Administration (8 endpoints)

Tenant-level administration operations.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecAddSPN` | |
| POST | `api/ExecOffboardTenant` | |
| POST | `api/ExecOnboardTenant` | |
| POST | `api/ExecUpdateSecureScore` | |
| GET | `api/ListAppConsentRequests` | |
| GET | `api/ListDomains` | |
| GET | `api/ListTenantOnboarding` | |
| POST | `api/SetAuthMethod` | |

## Tenant/Administration/Alerts (9 endpoints)

Audit log and webhook alert management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddAlert` | |
| POST | `api/ExecAuditLogSearch` | |
| GET | `api/ListAlertsQueue` | |
| GET | `api/ListAuditLogSearches` | |
| GET | `api/ListAuditLogTest` | |
| GET | `api/ListAuditLogs` | |
| GET | `api/ListWebhookAlert` | |
| POST | `api/PublicWebhooks` | |
| POST | `api/RemoveQueuedAlert` | |

## Tenant/Administration/Application Approval (7 endpoints)

Enterprise application and consent management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecAddMultiTenantApp` | |
| POST | `api/ExecAppApproval` | |
| POST | `api/ExecAppApprovalTemplate` | |
| POST | `api/ExecAppPermissionTemplate` | |
| POST | `api/ExecApplication` | |
| POST | `api/ExecCreateAppTemplate` | |
| GET | `api/ListAppApprovalTemplates` | |

## Tenant/Administration/Domains (2 endpoints)

Domain management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddDomain` | |
| POST | `api/ExecDomainAction` | |

## Tenant/Administration/Tenant (6 endpoints)

Tenant record management within CIPP.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddTenant` | |
| POST | `api/EditTenant` | |
| POST | `api/EditTenantOffboardingDefaults` | |
| GET | `api/ListTenantDetails` | |
| GET | `api/ListTenants` | |
| POST | `api/RemoveTenantCapabilitiesCache` | |

## Tenant/Conditional (13 endpoints)

Conditional Access policy management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddCAPolicy` | |
| POST | `api/AddCATemplate` | |
| POST | `api/AddNamedLocation` | |
| POST | `api/EditCAPolicy` | |
| POST | `api/ExecCACheck` | |
| POST | `api/ExecCAExclusion` | |
| POST | `api/ExecCAServiceExclusion` | |
| POST | `api/ExecNamedLocation` | |
| GET | `api/ListCAtemplates` | |
| GET | `api/ListConditionalAccessPolicies` | |
| GET | `api/ListConditionalAccessPolicyChanges` | |
| POST | `api/RemoveCAPolicy` | |
| POST | `api/RemoveCATemplate` | |

## Tenant/GDAP (12 endpoints)

Granular Delegated Admin Privileges management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecAddGDAPRole` | |
| POST | `api/ExecAutoExtendGDAP` | |
| POST | `api/ExecDeleteGDAPRelationship` | |
| POST | `api/ExecDeleteGDAPRoleMapping` | |
| POST | `api/ExecGDAPAccessAssignment` | |
| POST | `api/ExecGDAPInvite` | |
| POST | `api/ExecGDAPInviteApproved` | |
| POST | `api/ExecGDAPRemoveGArole` | |
| POST | `api/ExecGDAPRoleTemplate` | |
| GET | `api/ListGDAPAccessAssignments` | |
| GET | `api/ListGDAPInvite` | |
| GET | `api/ListGDAPRoles` | |

## Tenant/Reports (3 endpoints)

Tenant-level reports.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `api/ListLicenses` | |
| GET | `api/ListOAuthApps` | |
| GET | `api/ListServiceHealth` | |

## Tenant/Standards (23 endpoints)

Standards compliance, Best Practice Analyzer, and domain health.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddStandardsDeploy` | |
| POST | `api/AddStandardsTemplate` | |
| GET | `api/BestPracticeAnalyser_List` | |
| POST | `api/CIPPStandardsRun` | |
| GET | `api/DomainAnalyser_List` | |
| POST | `api/ExecBPA` | |
| POST | `api/ExecDomainAnalyser` | |
| POST | `api/ExecDriftClone` | |
| POST | `api/ExecStandardConvert` | |
| POST | `api/ExecStandardsRun` | |
| POST | `api/ExecUpdateDriftDeviation` | |
| GET | `api/ListBPA` | |
| GET | `api/ListBPATemplates` | |
| GET | `api/ListDomainAnalyser` | |
| GET | `api/ListDomainHealth` | |
| GET | `api/ListStandards` | |
| GET | `api/ListStandardsCompare` | |
| GET | `api/ListTenantAlignment` | |
| GET | `api/ListTenantDrift` | |
| POST | `api/RemoveBPATemplate` | |
| POST | `api/RemoveStandard` | |
| POST | `api/RemoveStandardTemplate` | |
| GET | `api/listStandardTemplates` | |

## Tenant/Tools (2 endpoints)

Tenant tools and utilities.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/AddBPATemplate` | |
| POST | `api/ExecGraphExplorerPreset` | |

## Tools/GitHub (4 endpoints)

Community repository and release management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `api/ExecCommunityRepo` | |
| POST | `api/ExecGitHubAction` | |
| GET | `api/ListCommunityRepos` | |
| GET | `api/ListGitHubReleaseNotes` | |

---

## HaloClaude Integration

Of these endpoints, HaloClaude currently integrates **17 tools** (12 read-only + 5 write).
See `cipp/tools.py` for the full tool definitions.

### Read-only (proxy + MCP + triage)
| CIPP Endpoint | HaloClaude Tool |
|--------------|----------------|
| `api/ListTenants` | `cipp_list_tenants` |
| `api/ListUsers` | `cipp_list_users` |
| `api/ListGroups` | `cipp_list_groups` |
| `api/ListUserGroups` | `cipp_list_user_groups` |
| `api/ListMailboxes` | `cipp_list_mailboxes` |
| `api/ListmailboxPermissions` | `cipp_list_mailbox_permissions` |
| `api/ListMailboxRules` | `cipp_list_mailbox_rules` |
| `api/ListDevices` | `cipp_list_devices` |
| `api/ListLicenses` | `cipp_list_licenses` |
| `api/ListSignIns` | `cipp_list_sign_ins` |
| `api/ListDefenderState` | `cipp_list_defender_state` |
| `api/ListConditionalAccessPolicies` | `cipp_list_conditional_access_policies` |

### Write/action (proxy + MCP only, NOT triage)
| CIPP Endpoint | HaloClaude Tool |
|--------------|----------------|
| `api/ExecResetPass` | `cipp_reset_password` |
| `api/ExecDisableUser` | `cipp_disable_user` |
| `api/ExecDeviceAction` | `cipp_device_action` |
| `api/ExecEditMailboxPermissions` | `cipp_edit_mailbox_permissions` |
| `api/ExecOffboardUser` | `cipp_offboard_user` |
