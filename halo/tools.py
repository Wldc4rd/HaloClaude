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
                "full history, status, priority, and all associated data. Use this "
                "when you need complete context about a ticket."
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
                "company affiliation, and role. Use this to understand who you're "
                "helping and their context."
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
                "service level, and configuration. Use this to understand the "
                "business context."
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
                "specifications, and history. Use this when the ticket involves "
                "specific hardware or devices."
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
    ]
