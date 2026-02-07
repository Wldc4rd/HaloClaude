"""
Mesh Email Security Tool Definitions for Claude

Defines the tools that Claude can use to query Mesh email logs.
These follow Claude's tool definition format and are used by the proxy agent.
"""

from typing import List, Dict, Any


def get_mesh_tools() -> List[Dict[str, Any]]:
    """
    Get the list of Mesh Email Security tools available to Claude.

    Returns:
        List of tool definitions in Claude format
    """
    return [
        {
            "name": "mesh_search_email_logs",
            "description": (
                "Search email logs in Mesh Email Security (Live Email Tracker). "
                "Use this to investigate email delivery issues, find quarantined/blocked "
                "emails, trace specific messages, or analyze email threats. "
                "Supports filtering by sender, recipient, subject, status, verdict, "
                "date range, sender IP, and message ID. "
                "Set direction to 'inbound' or 'outbound'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["inbound", "outbound"],
                        "description": (
                            "Email direction: 'inbound' for received emails, "
                            "'outbound' for sent emails. Defaults to 'inbound'."
                        ),
                    },
                    "from_addr": {
                        "type": "string",
                        "description": "Sender email address to filter by",
                    },
                    "to_addr": {
                        "type": "string",
                        "description": "Recipient email address to filter by",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line to search for",
                    },
                    "status": {
                        "type": "string",
                        "description": (
                            "Email status filter. Comma-separated values: "
                            "quarantine, bounce, defer, delete, banner"
                        ),
                    },
                    "verdict": {
                        "type": "string",
                        "description": "Email verdict/classification filter (e.g. spam, clean, malware)",
                    },
                    "start": {
                        "type": "string",
                        "description": "Start datetime in ISO format: YYYY-MM-DDTHH:mm:ss (defaults to 24 hours ago)",
                    },
                    "end": {
                        "type": "string",
                        "description": "End datetime in ISO format: YYYY-MM-DDTHH:mm:ss (defaults to now)",
                    },
                    "sender_ip": {
                        "type": "string",
                        "description": "Sender IP address to filter by",
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Specific email message ID to look up",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of results to return (default 50, max 150)",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "mesh_get_email_events",
            "description": (
                "Get the detailed event trace for a specific email from Mesh Email Security. "
                "Shows the full processing history: filtering decisions, delivery attempts, "
                "quarantine actions, etc. Requires a queue_id from the email log results."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "queue_id": {
                        "type": "integer",
                        "description": "The queue ID of the email (from email log search results)",
                    }
                },
                "required": ["queue_id"],
            },
        },
        {
            "name": "mesh_search_customers",
            "description": (
                "Search Mesh Email Security customers by company name or email domain. "
                "Use this to find a customer's Mesh account when investigating "
                "email issues for a specific organization."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "filter_term": {
                        "type": "string",
                        "description": "Search term: company name or email domain",
                    }
                },
                "required": ["filter_term"],
            },
        },
    ]
