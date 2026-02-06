"""
Context Formatter - Formats fetched data for injection into system prompts.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .fetcher import ContextData

logger = logging.getLogger(__name__)


class ContextFormatter:
    """Formats Halo context data for Claude's system prompt."""

    def __init__(
        self,
        max_sop_article_length: int = 2000,
        max_contract_doc_length: int = 5000,
    ):
        """
        Initialize the formatter.

        Args:
            max_sop_article_length: Max characters per SOP article content
            max_contract_doc_length: Max characters of extracted PDF text per contract
        """
        self.max_sop_article_length = max_sop_article_length
        self.max_contract_doc_length = max_contract_doc_length

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
        sections.append(
            "IMPORTANT: This context is provided as background reference only. "
            "You MUST follow the instructions in the system prompt above. "
            "If the system prompt asks for a structured report, analysis, summary, "
            "or any specific format, produce exactly that — do NOT write an email "
            "or client communication unless the system prompt specifically asks for one. "
            "The SOPs below are guidelines for when you ARE writing client-facing responses.\n\n"
            "**CRITICAL: When writing emails or responses, you MUST reference and incorporate "
            "the TICKET HISTORY below. This contains the actual conversation and work done on this ticket. "
            "Your response should directly relate to and build upon the recent actions and notes.**"
        )

        # Order: background info first, then ticket history last (Claude pays more attention to recent context)
        if context.ticket:
            sections.append(self._format_ticket(context.ticket))

        if context.user:
            sections.append(self._format_user(context.user))

        if context.client:
            sections.append(self._format_client(context.client))

        if context.contracts:
            sections.append(self._format_contracts(
                context.contracts, context.ticket, context.contract_doc_texts
            ))

        if context.assets:
            sections.append(self._format_assets(context.assets))

        if context.ninja_devices:
            sections.append(self._format_ninja_devices(context.ninja_devices))

        if context.related_tickets:
            sections.append(self._format_related_tickets(context.related_tickets))

        if context.sop_articles:
            sections.append(self._format_sop_articles(context.sop_articles))

        if context.errors:
            sections.append(self._format_errors(context.errors))

        # TICKET HISTORY LAST - most important for email generation
        if context.actions:
            sections.append(self._format_actions(context.actions))
            # Add a final reminder about recent work
            sections.append(self._format_recent_work_reminder(context.actions))

        sections.append("=" * 60)

        return "\n\n".join(sections)

    def _format_recent_work_reminder(self, actions: List[Dict[str, Any]]) -> str:
        """
        Add a prominent reminder about recent work done on the ticket.
        This helps Claude understand it should update the customer about completed work.
        """
        if not actions:
            return ""

        # Get the most recent action with note content
        sorted_actions = sorted(
            actions,
            key=lambda a: a.get("datetime", a.get("dateoccurred", a.get("date", ""))),
            reverse=True
        )

        recent_work = []
        for action in sorted_actions[:3]:  # Check top 3 most recent
            note = action.get("note", "")
            if note and len(note) > 50:  # Has substantial content
                who = action.get("who", "Unknown")
                outcome = action.get("outcome", "Note")
                if isinstance(outcome, dict):
                    outcome = outcome.get("name", "Note")
                # Get first 200 chars as summary
                summary = note[:200].replace("\n", " ")
                if len(note) > 200:
                    summary += "..."
                recent_work.append(f"- [{outcome}] by {who}: {summary}")

        if not recent_work:
            return ""

        lines = [
            "### ⚠️ IMPORTANT: RECENT WORK ON THIS TICKET",
            "**If you are writing a reply to the customer, you MUST inform them about the work described above.**",
            "**Do NOT just respond to their original question - update them on what has been done.**",
            "",
            "Most recent work:",
        ]
        lines.extend(recent_work)

        return "\n".join(lines)

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

    def _format_related_tickets(self, related: List[Dict[str, Any]]) -> str:
        """Format related/linked tickets."""
        lines = ["### RELATED TICKETS"]
        lines.append("The following tickets are linked to this ticket. Use the get_ticket tool to view full details.")

        for rt in related:
            tid = rt.get("id", "?")
            summary = rt.get("summary", "No summary")

            status = rt.get("status_name", rt.get("status", ""))
            if isinstance(status, dict):
                status = status.get("name", "")
            status_str = f" (Status: {status})" if status else ""

            lines.append(f"- Ticket #{tid}: {summary}{status_str}")

        return "\n".join(lines)

    def _format_actions(self, actions: List[Dict[str, Any]]) -> str:
        """Format ticket history/actions."""
        lines = [
            "### TICKET HISTORY (IMPORTANT - USE THIS FOR EMAIL CONTEXT)",
            "**The following is the actual conversation and work history for this ticket. "
            "Reference this when writing responses:**"
        ]

        if not actions:
            lines.append("No actions recorded.")
            return "\n".join(lines)

        # Debug: log sample of first action to see available fields
        if actions:
            sample = actions[0]
            logger.info(f"Sample action fields: {list(sample.keys())[:15]}...")  # First 15 fields
            logger.info(
                f"Sample action: datetime={sample.get('datetime')}, "
                f"who={sample.get('who')}, outcome={sample.get('outcome')}, "
                f"note_len={len(sample.get('note', '') or '')}"
            )
            # Count actions by type to see distribution
            private_count = sum(1 for a in actions if a.get("hiddenfromuser"))
            public_count = len(actions) - private_count
            has_note = sum(1 for a in actions if a.get("note"))
            has_emailbody = sum(1 for a in actions if a.get("emailbody"))
            logger.info(
                f"Action breakdown: {len(actions)} total, {private_count} private, {public_count} public, "
                f"{has_note} with note, {has_emailbody} with emailbody"
            )

        # Sort by date (newest first) and limit to recent actions
        # Halo uses 'datetime' field for actions
        sorted_actions = sorted(
            actions,
            key=lambda a: a.get("datetime", a.get("dateoccurred", a.get("date", ""))),
            reverse=True
        )

        # Limit to most recent 20 actions to avoid context overflow
        max_actions = 20
        if len(sorted_actions) > max_actions:
            lines.append(f"(Showing {max_actions} most recent of {len(sorted_actions)} actions)")
            sorted_actions = sorted_actions[:max_actions]

        # Debug: count actions with actual note content
        actions_with_notes = sum(1 for a in sorted_actions if a.get("note"))
        actions_with_emailbody = sum(1 for a in sorted_actions if a.get("emailbody"))
        logger.info(f"Formatting {len(sorted_actions)} actions: {actions_with_notes} with note, {actions_with_emailbody} with emailbody")

        for action in sorted_actions:
            action_id = action.get("id", "")
            action_type = action.get("outcome", action.get("actiontype", "Note"))
            if isinstance(action_type, dict):
                action_type = action_type.get("name", "Note")

            # Get who performed the action
            who = action.get("who", action.get("agent", ""))
            if isinstance(who, dict):
                who = who.get("name", "Unknown")

            # Get the date - Halo uses 'datetime' for actions
            date = action.get("datetime", action.get("dateoccurred", action.get("date", "Unknown date")))

            # Get the note/content - check multiple fields
            # Email actions use emailbody/emailbody_html, notes use note/note_html
            note = (
                action.get("note")
                or action.get("emailbody")
                or action.get("note_html")
                or action.get("emailbody_html")
                or action.get("details")
                or action.get("description")
                or ""
            )

            # Get email subject if present
            email_subject = action.get("emailsubject", "")

            # Strip HTML if present
            if note and "<" in note:
                note = re.sub(r"<[^>]+>", " ", note)
                note = re.sub(r"\s+", " ", note).strip()

            # Truncate long notes
            if note and len(note) > 500:
                note = note[:500] + "... [truncated]"

            lines.append(f"\n**[{date}] {action_type}** by {who}")
            if email_subject:
                lines.append(f"  Subject: {email_subject}")
            if note:
                lines.append(f"  {note}")

        # Log a sample of formatted output
        result = "\n".join(lines)
        if len(result) > 500:
            logger.info(f"Formatted TICKET HISTORY section ({len(result)} chars). First 500: {result[:500]}")
        else:
            logger.info(f"Formatted TICKET HISTORY section: {result}")

        return result

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
        contract_doc_texts: Optional[Dict[int, str]] = None,
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

            # Contract type
            contract_type = contract.get("contracttype_name", "")
            if contract_type:
                lines.append(f"  - Type: {contract_type}")

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

            # Prepaid hours (from contract detail endpoint)
            hrs_total = contract.get("contract_prepaytotal", 0)
            hrs_used = contract.get("contract_prepayused", 0)
            hrs_remaining = contract.get("contract_prepaybalance", 0)
            if hrs_total > 0:
                lines.append(
                    f"  - Prepaid Hours: {hrs_total} total, "
                    f"{hrs_used} used, {hrs_remaining} remaining"
                )

            # Contract note
            note = contract.get("note", "")
            if note:
                if len(note) > 300:
                    note = note[:300] + "... [truncated]"
                lines.append(f"  - Notes: {note}")

            # Contract document text (extracted from PDF)
            contract_id = contract.get("id")
            if contract_doc_texts and contract_id in contract_doc_texts:
                doc_text = contract_doc_texts[contract_id]
                if len(doc_text) > self.max_contract_doc_length:
                    doc_text = doc_text[:self.max_contract_doc_length] + "\n... [truncated]"
                lines.append(f"  - Agreement Document:\n{doc_text}")

        return "\n".join(lines)

    def _format_sop_articles(self, articles: List[Dict[str, Any]]) -> str:
        """Format SOP KB articles for injection."""
        lines = ["### STANDARD OPERATING PROCEDURES"]
        lines.append("The following business process guidelines apply when writing client-facing responses:")

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

    def _format_ninja_devices(self, ninja_devices: Dict[int, Dict[str, Any]]) -> str:
        """Format live NinjaRMM device data."""
        lines = ["### LIVE DEVICE DATA (from NinjaRMM)"]
        lines.append("Real-time device monitoring data from NinjaRMM:")

        for device_id, data in ninja_devices.items():
            device = data.get("device", {})
            volumes = data.get("volumes", [])
            alerts = data.get("alerts", [])
            os_patches = data.get("os_patches", [])

            # Device name and basic info
            system_name = device.get("systemName", device.get("dnsName", f"Device {device_id}"))
            lines.append(f"\n**Device: {system_name}** (NinjaRMM ID: {device_id})")

            # Online/offline status
            offline = device.get("offline")
            if offline is not None:
                status = "Offline" if offline else "Online"
                lines.append(f"  - Status: {status}")

            last_contact = device.get("lastContact")
            if last_contact:
                lines.append(f"  - Last Contact: {last_contact}")

            # OS info
            os_info = device.get("os", {})
            if isinstance(os_info, dict):
                os_name = os_info.get("name", "")
                if os_name:
                    lines.append(f"  - OS: {os_name}")
            elif isinstance(os_info, str) and os_info:
                lines.append(f"  - OS: {os_info}")

            # Node class / device type
            node_class = device.get("nodeClass", "")
            if node_class:
                lines.append(f"  - Type: {node_class}")

            # IP addresses
            ip_addrs = device.get("ipAddresses", [])
            if ip_addrs:
                lines.append(f"  - IP Addresses: {', '.join(str(ip) for ip in ip_addrs)}")

            # Disk volumes
            if volumes:
                lines.append("  - Disk Volumes:")
                for vol in volumes:
                    name = vol.get("name", vol.get("letter", "?"))
                    capacity = vol.get("capacity", 0)
                    free = vol.get("freeSpace", 0)
                    if capacity > 0:
                        capacity_gb = capacity / (1024 ** 3)
                        free_gb = free / (1024 ** 3)
                        pct_free = (free / capacity) * 100
                        lines.append(
                            f"    - {name}: {free_gb:.1f} GB free / {capacity_gb:.1f} GB total "
                            f"({pct_free:.0f}% free)"
                        )

            # Active alerts
            if alerts:
                lines.append(f"  - Active Alerts ({len(alerts)}):")
                for alert in alerts[:5]:  # Limit to 5 alerts
                    severity = alert.get("severity", "UNKNOWN")
                    message = alert.get("message", alert.get("subject", "No description"))
                    lines.append(f"    - [{severity}] {message}")
                if len(alerts) > 5:
                    lines.append(f"    - ... and {len(alerts) - 5} more")

            # Pending patches
            if os_patches:
                lines.append(f"  - Pending OS Patches: {len(os_patches)}")

        return "\n".join(lines)

    def _format_errors(self, errors: List[str]) -> str:
        """Format any errors that occurred during fetching."""
        lines = ["### FETCH WARNINGS"]
        lines.append("Some context could not be fetched:")
        for error in errors:
            lines.append(f"  - {error}")
        return "\n".join(lines)
