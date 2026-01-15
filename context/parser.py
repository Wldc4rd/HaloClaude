"""
Ticket ID Parser - Extracts ticket IDs from Halo system prompts.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Regex patterns for extracting ticket IDs from system prompts
# Ordered by specificity (most specific first)
TICKET_ID_PATTERNS = [
    r"Ticket\s*#\s*(\d+)",              # "Ticket #123", "Ticket # 123"
    r"Ticket\s+(\d+)",                   # "Ticket 123"
    r"ticket[_\s]?id[:\s]+(\d+)",        # "ticket_id: 123", "ticket id: 123"
    r"\[Ticket:\s*(\d+)\]",              # "[Ticket: 123]"
    r"/tickets/(\d+)",                   # URL format "/tickets/123"
    r"(?<!\d)#(\d{4,})(?!\d)",           # "#12345" (4+ digits, not part of larger number)
]


class TicketIdParser:
    """Extracts ticket IDs from Halo system prompts."""

    def __init__(self, patterns: Optional[list] = None):
        """
        Initialize the parser.

        Args:
            patterns: Custom regex patterns (optional, uses defaults if not provided)
        """
        self.patterns = patterns or TICKET_ID_PATTERNS
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def parse(self, system_prompt: str) -> Optional[int]:
        """
        Extract ticket ID from system prompt.

        Args:
            system_prompt: The system prompt text from Halo

        Returns:
            Ticket ID if found, None otherwise
        """
        if not system_prompt:
            return None

        for pattern in self._compiled:
            match = pattern.search(system_prompt)
            if match:
                ticket_id = int(match.group(1))
                logger.debug(f"Found ticket ID {ticket_id} using pattern: {pattern.pattern}")
                return ticket_id

        logger.debug("No ticket ID found in system prompt")
        return None
