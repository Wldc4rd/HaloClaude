"""
Context Formatter - Formats fetched data for injection into system prompts.
"""

import re
from typing import Any, Dict, List, Optional

from .fetcher import ContextData


class ContextFormatter:
    """Formats Halo context data for Claude's system prompt."""

    def __init__(self, max_sop_article_length: int = 2000):
        """
        Initialize the formatter.

        Args:
            max_sop_article_length: Max characters per SOP article content
        """
        self.max_sop_article_length = max_sop_article_length

    def format(self, context: ContextData) -> str:
        """
        Format context data into a readable string for injection.

        Args:
            context: The fetched context data

        Returns:
            Formatted string to append to system prompt
        """
        sections = []

        sections.append("=" * 60)
        sections.append("ADDITIONAL CONTEXT FROM HALO (Pre-fetched)")
        sections.append("=" * 60)

        if context.ticket:
            sections.append(self._format_ticket(context.ticket))

        if context.actions:
            sections.append(self._format_actions(context.actions))

        if context.user:
            sections.append(self._format_user(context.user))

        if context.client:
            sections.append(self._format_client(context.client))

        if context.contracts:
            sections.append(self._format_contracts(context.contracts, context.ticket))

        if context.assets:
            sections.append(self._format_assets(context.assets))

        if context.sop_articles:
            sections.append(self._format_sop_articles(context.sop_articles))

        if context.errors:
            sections.append(self._format_errors(context.errors))

        sections.append("=" * 60)

        return "\n\n".join(sections)

    def _format_ticket(self, ticket: Dict[str, Any]) -> str:
        """Format ticket details."""
        lines = ["### TICKET DETAILS"]

        # Basic info
        lines.append(f"- ID: {ticket.get('id', 'Unknown')}")
        lines.append(f"- Summary: {ticket.get('summary', 'No summary')}")

        # Status (can be string or object)
        status = ticket.get("status")
        if isinstance(status, dict):
            status = status.get("name", "Unknown")
        lines.append(f"- Status: {status or 'Unknown'}")

        # Priority (can be string or object)
        priority = ticket.get("priority")
        if isinstance(priority, dict):
            priority = priority.get("name", "Unknown")
        lines.append(f"- Priority: {priority or 'Unknown'}")

        # Ticket type
        ticket_type = ticket.get("tickettype")
        if isinstance(ticket_type, dict):
            ticket_type = ticket_type.get("name", "Unknown")
        lines.append(f"- Type: {ticket_type or 'Unknown'}")

        # Dates
        if ticket.get("dateoccurred"):
            lines.append(f"- Created: {ticket['dateoccurred']}")
        if ticket.get("datelastevent"):
            lines.append(f"- Last Updated: {ticket['datelastevent']}")

        # Details/description
        details = ticket.get("details", ticket.get("description", ""))
        if details:
            # Truncate very long details
            if len(details) > 1000:
                details = details[:1000] + "... [truncated]"
            lines.append(f"- Details: {details}")

        return "\n".join(lines)

    def _format_actions(self, actions: List[Dict[str, Any]]) -> str:
        """Format ticket history/actions."""
        lines = ["### TICKET HISTORY"]

        if not actions:
            lines.append("No actions recorded.")
            return "\n".join(lines)

        # Sort by date (newest first) and limit to recent actions
        sorted_actions = sorted(
            actions,
            key=lambda a: a.get("dateoccurred", a.get("date", "")),
            reverse=True
        )

        # Limit to most recent 20 actions to avoid context overflow
        max_actions = 20
        if len(sorted_actions) > max_actions:
            lines.append(f"(Showing {max_actions} most recent of {len(sorted_actions)} actions)")
            sorted_actions = sorted_actions[:max_actions]

        for action in sorted_actions:
            action_id = action.get("id", "")
            action_type = action.get("outcome", action.get("actiontype", "Note"))
            if isinstance(action_type, dict):
                action_type = action_type.get("name", "Note")

            # Get who performed the action
            who = action.get("who", action.get("agent", ""))
            if isinstance(who, dict):
                who = who.get("name", "Unknown")

            # Get the date
            date = action.get("dateoccurred", action.get("date", "Unknown date"))

            # Get the note/content
            note = action.get("note", action.get("details", action.get("description", "")))
            # Strip HTML if present
            if note and "<" in note:
                note = re.sub(r"<[^>]+>", " ", note)
                note = re.sub(r"\s+", " ", note).strip()
            # Truncate long notes
            if note and len(note) > 500:
                note = note[:500] + "... [truncated]"

            lines.append(f"\n**[{date}] {action_type}** by {who}")
            if note:
                lines.append(f"  {note}")

        return "\n".join(lines)

    def _format_user(self, user: Dict[str, Any]) -> str:
        """Format user information."""
        lines = ["### USER INFORMATION"]

        lines.append(f"- Name: {user.get('name', 'Unknown')}")

        if user.get("emailaddress"):
            lines.append(f"- Email: {user['emailaddress']}")

        if user.get("phonenumber"):
            lines.append(f"- Phone: {user['phonenumber']}")

        if user.get("jobtitle"):
            lines.append(f"- Job Title: {user['jobtitle']}")

        if user.get("isvip"):
            lines.append("- VIP: Yes")

        # Site/location
        site = user.get("site")
        if isinstance(site, dict):
            site = site.get("name")
        if site:
            lines.append(f"- Site: {site}")

        return "\n".join(lines)

    def _format_client(self, client: Dict[str, Any]) -> str:
        """Format client/company information."""
        lines = ["### CLIENT/COMPANY INFORMATION"]

        lines.append(f"- Name: {client.get('name', 'Unknown')}")

        if client.get("website"):
            lines.append(f"- Website: {client['website']}")

        if client.get("phonenumber"):
            lines.append(f"- Phone: {client['phonenumber']}")

        # SLA
        sla = client.get("sla")
        if isinstance(sla, dict):
            sla = sla.get("name")
        if sla:
            lines.append(f"- SLA: {sla}")

        # Main contact
        if client.get("main_contact"):
            lines.append(f"- Main Contact: {client['main_contact']}")

        # Notes (truncated)
        notes = client.get("notes", "")
        if notes:
            if len(notes) > 500:
                notes = notes[:500] + "... [truncated]"
            lines.append(f"- Notes: {notes}")

        return "\n".join(lines)

    def _format_contracts(
        self,
        contracts: List[Dict[str, Any]],
        ticket: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format contract information."""
        lines = ["### CONTRACT INFORMATION"]

        if not contracts:
            lines.append("No contracts found for this client.")
            return "\n".join(lines)

        # Get ticket's contract ID for highlighting
        ticket_contract_id = None
        if ticket:
            ticket_contract_id = ticket.get("contract_id")
            if isinstance(ticket_contract_id, dict):
                ticket_contract_id = ticket_contract_id.get("id")

        # Filter to active contracts (plus the ticket's contract even if expired)
        active_contracts = [
            c for c in contracts
            if not c.get("expired", False) or c.get("id") == ticket_contract_id
        ]

        if not active_contracts:
            lines.append("No active contracts.")
            return "\n".join(lines)

        # Sort: ticket's contract first
        active_contracts.sort(
            key=lambda c: (c.get("id") != ticket_contract_id, c.get("ref", ""))
        )

        for contract in active_contracts:
            is_ticket_contract = contract.get("id") == ticket_contract_id
            ref = contract.get("ref", f"Contract {contract.get('id', '?')}")

            label = f"**{ref}**"
            if is_ticket_contract:
                label += " (Ticket's Contract)"
            lines.append(f"\n{label}")

            # SLA
            sla_name = contract.get("sla_name")
            if sla_name:
                lines.append(f"  - SLA: {sla_name}")

            # Dates
            start = contract.get("start_date", "")
            end = contract.get("end_date", "")
            if start or end:
                date_str = f"{start[:10] if start else '?'} to {end[:10] if end else 'ongoing'}"
                lines.append(f"  - Period: {date_str}")

            # Status
            started = contract.get("started", False)
            expired = contract.get("expired", False)
            if started and not expired:
                lines.append("  - Status: Active")
            elif expired:
                lines.append("  - Status: Expired")
            elif not started:
                lines.append("  - Status: Not Started")

            # Prepaid hours from periods
            periods = contract.get("periods", [])
            current_period = None
            for period in periods:
                if period.get("current"):
                    current_period = period
                    break
            if not current_period and periods:
                current_period = periods[-1]

            if current_period:
                hrs_total = current_period.get("hours_in_period", 0)
                hrs_used = current_period.get("hours_used", 0)
                hrs_remaining = current_period.get("hours_remaining", 0)
                if hrs_total > 0:
                    lines.append(
                        f"  - Prepaid Hours: {hrs_total} total, "
                        f"{hrs_used} used, {hrs_remaining} remaining"
                    )

            # Billing indicators
            if contract.get("allowprepay"):
                lines.append("  - Type: Prepaid Hours Contract")
            elif contract.get("allowpyg"):
                lines.append("  - Type: Pay As You Go")

            # Contract note
            note = contract.get("note", "")
            if note:
                if len(note) > 300:
                    note = note[:300] + "... [truncated]"
                lines.append(f"  - Notes: {note}")

        return "\n".join(lines)

    def _format_sop_articles(self, articles: List[Dict[str, Any]]) -> str:
        """Format SOP KB articles for injection."""
        lines = ["### STANDARD OPERATING PROCEDURES"]
        lines.append("The following business process guidelines apply:")

        for i, article in enumerate(articles, 1):
            title = article.get("name", article.get("title", f"Article {i}"))

            lines.append(f"\n**{title}**")

            # Get article content — try multiple field names
            content = (
                article.get("resolution")
                or article.get("description")
                or article.get("resolution_html")
                or article.get("description_html")
                or ""
            )

            # Strip HTML if present
            if content and "<" in content:
                content = re.sub(r"<[^>]+>", " ", content)
                content = re.sub(r"\s+", " ", content).strip()

            if content:
                if len(content) > self.max_sop_article_length:
                    content = content[:self.max_sop_article_length] + "... [truncated]"
                lines.append(f"  {content}")

        return "\n".join(lines)

    def _format_assets(self, assets: List[Dict[str, Any]]) -> str:
        """Format linked assets."""
        lines = ["### LINKED ASSETS"]

        for i, asset in enumerate(assets, 1):
            name = asset.get("name", asset.get("inventory_number", f"Asset {i}"))
            lines.append(f"\n**Asset {i}: {name}**")

            # Asset type
            asset_type = asset.get("assettype")
            if isinstance(asset_type, dict):
                asset_type = asset_type.get("name")
            if asset_type:
                lines.append(f"  - Type: {asset_type}")

            if asset.get("serialnumber"):
                lines.append(f"  - Serial: {asset['serialnumber']}")

            if asset.get("manufacturer"):
                lines.append(f"  - Manufacturer: {asset['manufacturer']}")

            if asset.get("model"):
                lines.append(f"  - Model: {asset['model']}")

            # Status
            status = asset.get("status")
            if isinstance(status, dict):
                status = status.get("name")
            if status:
                lines.append(f"  - Status: {status}")

            # Hostname/IP
            if asset.get("hostname"):
                lines.append(f"  - Hostname: {asset['hostname']}")

            if asset.get("ipaddress"):
                lines.append(f"  - IP Address: {asset['ipaddress']}")

        return "\n".join(lines)

    def _format_errors(self, errors: List[str]) -> str:
        """Format any errors that occurred during fetching."""
        lines = ["### FETCH WARNINGS"]
        lines.append("Some context could not be fetched:")
        for error in errors:
            lines.append(f"  - {error}")
        return "\n".join(lines)
