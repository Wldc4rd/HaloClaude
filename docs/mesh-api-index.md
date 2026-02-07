# Mesh Email Security API Reference

Base URL: `https://hub-us.emailsecurity.app`
OpenAPI spec (partial): `docs/Mesh-API-v1.json`

## Authentication

Two methods supported on all endpoints (use one):

- **API Key**: `API-KEY: {key}` header (static key from Mesh settings page)
- **Bearer JWT**: `Authorization: Bearer {token}` header

## Endpoints

### Email Logs (Live Email Tracker)

#### `GET /api/emaillogs/` — Search inbound email logs

#### `GET /api/emaillogs-outbound/` — Search outbound email logs

Both endpoints share the same query parameters:

| Parameter    | Type    | Description |
|-------------|---------|-------------|
| `from`      | string  | Sender email address |
| `to`        | string  | Recipient email address |
| `subject`   | string  | Email subject line |
| `status`    | string  | Comma-separated: `quarantine`, `bounce`, `defer`, `delete`, `banner` |
| `verdict`   | string  | Spam/clean/malware classification |
| `service`   | string  | Service type filter |
| `start`     | string  | Start datetime, ISO format: `YYYY-MM-DDTHH:mm:ss` |
| `end`       | string  | End datetime, ISO format: `YYYY-MM-DDTHH:mm:ss` |
| `message_id`| string  | Specific email message ID |
| `queue_id`  | string  | Queue ID |
| `sender_ip` | string  | Sender IP address |
| `_from`     | integer | Pagination offset (0-indexed) |
| `_size`     | integer | Page size (results per page) |
| `_max`      | integer | Max results (mutually exclusive with `_size`) |
| `_refresh`  | boolean | Refresh data before querying (1/0) |
| `format`    | string  | `json` or `txt` |

> **Note**: The `from`, `to`, `subject`, `status`, `verdict`, `service`, `start`, `end`, `message_id`, `queue_id`, and `sender_ip` parameters are undocumented in the OpenAPI spec. They were discovered by capturing browser requests from the Mesh web UI.

#### `GET /api/emaillogs/events` — Get email event trace

| Parameter  | Type    | Required | Description |
|-----------|---------|----------|-------------|
| `queue_id`| integer | Yes      | Queue ID of the email to get events for |
| `format`  | string  | No       | `json` or `txt` |

#### `GET /api/emaillogs/export-download` — Download email log export

| Parameter   | Type   | Required | Description |
|------------|--------|----------|-------------|
| `blob_name`| string | Yes      | Name of the export blob |
| `format`   | string | No       | `json` or `txt` |

### Customers

#### `GET /api/customers/` — List/search customers

| Parameter       | Type    | Description |
|----------------|---------|-------------|
| `filter`       | string  | Search by company_name or domain |
| `filter_service`| integer | 1=Mesh Gateway, 2=Mesh 365, 3=Mesh Unified |
| `filter_switch` | string  | `active`, `inactive`, or `trial` |
| `sorting`      | string  | Sort field (default: `company_name`) |
| `_from`        | integer | Pagination offset |
| `_size`        | integer | Page size |
| `format`       | string  | `json` or `txt` |

Response: `PaginatedCustomerList` with `count`, `next`, `previous`, `results[]`

#### `GET /api/customers/{id}/` — Get single customer

Path param `id` is a UUID.

#### `PATCH /api/customers/{id}/` — Update customer

Can update `company_name` and license count.

### Users

#### `GET /api/users/` — List/search users
#### `POST /api/users/` — Create user
#### `GET /api/users/{id}/` — Get user
#### `PATCH /api/users/{id}/` — Update user
#### `DELETE /api/users/{id}/` — Delete user
#### `GET /api/users/{id}/clear_2fa/` — Clear 2FA
#### `GET /api/users/customer/{customer_id}/` — List users for customer
#### `POST /api/users/customer/{customer_id}/import/` — Import users
#### `GET /api/users/staff-users/` — List staff users

### Audit Logs

#### `GET /api/auditlogs/` — Retrieve audit log history

| Parameter | Type    | Description |
|----------|---------|-------------|
| `_from`  | integer | Pagination offset |
| `_size`  | integer | Page size |
| `format` | string  | `json` or `txt` |

### Reports

#### `GET /api/reports/` — Retrieve reports

| Parameter | Type   | Description |
|----------|--------|-------------|
| `report` | string | Type of report |
| `format` | string | `json` or `txt` |

### Global Allow/Block Rules

#### `GET /api/global-allow-block-rules/` — List rules
#### `POST /api/global-allow-block-rules/` — Create rule
#### `GET /api/global-allow-block-rules/{id}/` — Get rule
#### `PATCH /api/global-allow-block-rules/{id}/` — Update rule
#### `DELETE /api/global-allow-block-rules/{id}/` — Delete rule

## Key Schemas

### Customer
- `id` (UUID), `company_name`, `active` (bool), `primary_domain`, `secondary_domains`
- `email_platform_name`, `user_count`, `licenses_billed`, `licenses_service`
- `auto_remediation`, `enforce_remediation`, `suspended`
- `date_created`, `date_modified`

### RuleAllowBlockGlobal
- `id` (UUID), `ab` (bool = allow/block), `active` (bool), `sender` (string)
- `comment`, `date_expiry`, `customer_id`, `partner_id`
- `edge` (bool), `organization_level` (bool), `set_by_partner` (bool)

### User
- `id` (UUID), `email`, `first_name`, `last_name`, `user_aliases[]`
- `customer`, `customer_id`, `policy`, `groups[]`
- `approved`, `is_active`, `vip`, `uses_2fa`
