"""
Halo Tool Definitions for Claude

Defines the tools that Claude can use to interact with Halo PSA.
These follow Claude's tool definition format.
"""

from typing import List, Dict, Any


def get_halo_tools() -> List[Dict[str, Any]]:
    """
    Get the list of Halo tools available to Claude.
    
    Returns:
        List of tool definitions in Claude format
    """
    return [
        {
            "name": "get_ticket",
            "description": (
                "Get detailed information about a specific ticket including its "
                "full history, status, priority, and all associated data. "
                "NOTE: The current ticket's data has been pre-fetched and is in the "
                "context above. Use this tool only for OTHER tickets."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID number",
                    }
                },
                "required": ["ticket_id"],
            },
        },
        {
            "name": "get_user",
            "description": (
                "Get information about a user including their contact details, "
                "company affiliation, and role. "
                "NOTE: The current ticket's user data has been pre-fetched and is in the "
                "context above. Use this tool only for OTHER users."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID number",
                    }
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "get_user_tickets",
            "description": (
                "Get a list of other tickets for a specific user. Use this to see "
                "if the user has related issues or a pattern of problems that might "
                "inform your response."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID number",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 10)",
                        "default": 10,
                    },
                    "open_only": {
                        "type": "boolean",
                        "description": "Only return open/active tickets",
                        "default": False,
                    },
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "get_client",
            "description": (
                "Get information about a client/company including their details, "
                "service level, and configuration. "
                "NOTE: The current ticket's client/company data has been pre-fetched "
                "and is in the context above. Use this tool only for OTHER clients."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": "The client/company ID number",
                    }
                },
                "required": ["client_id"],
            },
        },
        {
            "name": "get_client_tickets",
            "description": (
                "Get a list of recent tickets for a client/company. Use this to "
                "see if there are company-wide issues or patterns that relate to "
                "the current ticket."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": "The client/company ID number",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 10)",
                        "default": 10,
                    },
                    "open_only": {
                        "type": "boolean",
                        "description": "Only return open/active tickets",
                        "default": False,
                    },
                },
                "required": ["client_id"],
            },
        },
        {
            "name": "get_asset",
            "description": (
                "Get information about an asset/device including its configuration, "
                "specifications, and history. "
                "NOTE: Assets linked to the current ticket have been pre-fetched "
                "and are in the context above. Use this tool only for OTHER assets."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "asset_id": {
                        "type": "integer",
                        "description": "The asset ID number",
                    }
                },
                "required": ["asset_id"],
            },
        },
        {
            "name": "search_tickets",
            "description": (
                "Search for tickets matching a query. Use this to find related "
                "tickets, similar issues, or past resolutions that might help."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., error message, topic, keyword)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10,
                    },
                    "client_id": {
                        "type": "integer",
                        "description": "Filter results to a specific client/company",
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "Filter results to a specific user",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "search_kb",
            "description": (
                "Search the knowledge base for articles matching a query. Use this "
                "to find documented solutions, procedures, or information that might "
                "help resolve the issue."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for knowledge base articles",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_kb_article",
            "description": (
                "Get the full content of a specific knowledge base article. Use this "
                "after searching the KB to get complete article details."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "integer",
                        "description": "The knowledge base article ID",
                    }
                },
                "required": ["article_id"],
            },
        },
        {
            "name": "get_client_contracts",
            "description": (
                "Get contracts for a client/company, including contract type, SLA, "
                "prepaid hour balances, and billing details. "
                "NOTE: The current ticket's client contracts have been pre-fetched "
                "and are in the context above. Use this tool only for OTHER clients."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": "The client/company ID number",
                    }
                },
                "required": ["client_id"],
            },
        },
        {
            "name": "get_recurring_invoices",
            "description": (
                "Get recurring invoices for a contract or client. Returns the "
                "actual billed line items with descriptions, quantities, and "
                "prices. This is the definitive source of truth for what "
                "services a client is paying for on a contract."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "integer",
                        "description": "Filter by contract ID",
                    },
                    "client_id": {
                        "type": "integer",
                        "description": "Filter by client/company ID",
                    },
                },
            },
        },
        {
            "name": "set_ticket_priority",
            "description": (
                "Set the priority on a ticket. Priority IDs: "
                "1 = Critical, 2 = High, 3 = Medium, 4 = Low. "
                "The SLA is normally inherited from the client's contract "
                "and should not be changed unless it is clearly incorrect."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to update",
                    },
                    "priority_id": {
                        "type": "integer",
                        "description": (
                            "Priority level: 1=Critical, 2=High, 3=Medium, 4=Low"
                        ),
                        "enum": [1, 2, 3, 4],
                    },
                    "sla_id": {
                        "type": "integer",
                        "description": (
                            "SLA ID (only set if the current SLA is incorrect). "
                            "1=Default, 3=Bronze/Break-Fix, "
                            "4=Managed Gold, 5=Managed Silver"
                        ),
                    },
                },
                "required": ["ticket_id", "priority_id"],
            },
        },
        {
            "name": "create_ticket",
            "description": (
                "Create a new ticket in Halo PSA. Requires a summary and client_id. "
                "Optionally provide details, user, priority, type, and categories."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Ticket summary/subject line",
                    },
                    "client_id": {
                        "type": "integer",
                        "description": "Client/company ID",
                    },
                    "details": {
                        "type": "string",
                        "description": "Ticket description/details (supports HTML)",
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "Reporting user ID",
                    },
                    "priority_id": {
                        "type": "integer",
                        "description": "Priority level ID",
                    },
                    "ticket_type_id": {
                        "type": "integer",
                        "description": "Ticket type ID",
                    },
                    "category_1": {
                        "type": "string",
                        "description": "Primary category",
                    },
                    "category_2": {
                        "type": "string",
                        "description": "Secondary category",
                    },
                },
                "required": ["summary", "client_id"],
            },
        },
        {
            "name": "update_ticket",
            "description": (
                "Update fields on an existing ticket. Provide ticket_id and any "
                "fields to change. Only provided fields will be updated."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to update",
                    },
                    "summary": {
                        "type": "string",
                        "description": "New summary/subject line",
                    },
                    "details": {
                        "type": "string",
                        "description": "New description/details (supports HTML)",
                    },
                    "priority_id": {
                        "type": "integer",
                        "description": "New priority level ID",
                    },
                    "ticket_type_id": {
                        "type": "integer",
                        "description": "New ticket type ID",
                    },
                    "category_1": {
                        "type": "string",
                        "description": "New primary category",
                    },
                    "category_2": {
                        "type": "string",
                        "description": "New secondary category",
                    },
                    "agent_id": {
                        "type": "integer",
                        "description": "New assigned agent ID",
                    },
                    "team_id": {
                        "type": "integer",
                        "description": "New assigned team ID",
                    },
                    "status_id": {
                        "type": "integer",
                        "description": "New status ID",
                    },
                },
                "required": ["ticket_id"],
            },
        },
        {
            "name": "close_ticket",
            "description": (
                "Close/resolve a ticket. Optionally include a private closure note "
                "summarizing the resolution."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to close",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional closure/resolution note (private by default)",
                    },
                },
                "required": ["ticket_id"],
            },
        },
        {
            "name": "create_ticket_note",
            "description": (
                "Create or update a note on a ticket. "
                "To create a new note, provide ticket_id and note. "
                "To update an existing note, also provide action_id. "
                "Defaults to a private/agent-only note. "
                "Set hiddenfromuser to false to make the note visible to the end user."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to add the note to",
                    },
                    "note": {
                        "type": "string",
                        "description": "The note content (supports HTML)",
                    },
                    "hiddenfromuser": {
                        "type": "boolean",
                        "description": "If true, note is private/agent-only (default: true)",
                        "default": True,
                    },
                    "action_id": {
                        "type": "integer",
                        "description": "The action ID to update. Omit to create a new note.",
                    },
                },
                "required": ["ticket_id", "note"],
            },
        },
        {
            "name": "list_tickets",
            "description": (
                "List tickets with structured filters. Unlike search_tickets (keyword search), "
                "this filters by client, status (open/closed), date ranges, assigned agent, "
                "or linked asset. Returns summary-level data including status, priority, agent, "
                "and last action date. Use for browsing/filtering tickets rather than keyword searching."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": "Filter by client/company ID",
                    },
                    "open_only": {
                        "type": "boolean",
                        "description": "Only return open/active tickets (default: false)",
                    },
                    "closed_only": {
                        "type": "boolean",
                        "description": "Only return closed tickets (default: false)",
                    },
                    "agent_id": {
                        "type": "integer",
                        "description": "Filter by assigned agent ID",
                    },
                    "asset_id": {
                        "type": "integer",
                        "description": "Filter by linked asset ID",
                    },
                    "opened_after": {
                        "type": "string",
                        "description": "Only tickets opened after this date (ISO format, e.g. '2025-01-01')",
                    },
                    "opened_before": {
                        "type": "string",
                        "description": "Only tickets opened before this date (ISO format)",
                    },
                    "last_updated_after": {
                        "type": "string",
                        "description": "Only tickets last updated after this date (ISO format)",
                    },
                    "last_updated_before": {
                        "type": "string",
                        "description": "Only tickets last updated before this date (ISO format)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum results to return (default 25, max 100)",
                    },
                },
            },
        },
        {
            "name": "batch_close_tickets",
            "description": (
                "Close multiple tickets at once with a shared closure note. "
                "Use this when you need to close several related or stale tickets. "
                "Returns a summary showing which tickets were successfully closed and any failures."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of ticket IDs to close",
                    },
                    "note": {
                        "type": "string",
                        "description": "Closure note applied to all tickets (private by default)",
                    },
                },
                "required": ["ticket_ids"],
            },
        },
        {
            "name": "get_client_users",
            "description": (
                "List users belonging to a client/company. By default returns only active users. "
                "Set include_inactive to true to also see departed/disabled employees. "
                "The active/inactive status in the response indicates whether a user is current."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": "The client/company ID",
                    },
                    "include_active": {
                        "type": "boolean",
                        "description": "Include active users (default: true)",
                    },
                    "include_inactive": {
                        "type": "boolean",
                        "description": "Include inactive/departed users (default: false)",
                    },
                    "search": {
                        "type": "string",
                        "description": "Text search filter (name, email, etc.)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 50)",
                    },
                },
                "required": ["client_id"],
            },
        },
        {
            "name": "search_assets",
            "description": (
                "Search for assets/devices in Halo PSA by name, hostname, or other text. "
                "Optionally filter by client/company. Returns asset summaries including "
                "name, type, client, and status."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Text search (asset name, hostname, etc.)",
                    },
                    "client_id": {
                        "type": "integer",
                        "description": "Filter by client/company ID",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 50)",
                    },
                },
            },
        },
        {
            "name": "get_related_tickets",
            "description": (
                "Get tickets that are linked/related to a specific ticket. "
                "Use this to find associated issues, parent/child relationships, "
                "or tickets that have been manually linked together."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to find related tickets for",
                    },
                },
                "required": ["ticket_id"],
            },
        },
    ]
