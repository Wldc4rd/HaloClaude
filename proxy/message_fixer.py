"""
Message Fixer - Handles malformed message arrays from Halo PSA.

Halo PSA sometimes sends messages that Claude's API rejects:
1. Empty content in messages
2. Conversations ending with assistant messages (Claude interprets as prefill)

This module fixes these issues before sending to Claude.
"""

import copy
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class MessageFixer:
    """Fixes malformed message arrays for Claude compatibility."""
    
    EMPTY_CONTENT_REPLACEMENT = (
        "Please provide your response based on the instructions above."
    )
    
    ASSISTANT_ENDING_APPEND = (
        "Now provide your response based on the instructions and conversation above."
    )
    
    def fix_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fix message array for Claude compatibility.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Fixed message list (copy of original, original is not modified)
        """
        if not messages:
            return messages

        # Create a deep copy to avoid mutating the input
        messages = copy.deepcopy(messages)

        # Fix empty content
        messages = self._fix_empty_content(messages)
        
        # Fix assistant ending
        messages = self._fix_assistant_ending(messages)
        
        return messages
    
    def _fix_empty_content(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Replace empty message content with placeholder text."""
        for i, msg in enumerate(messages):
            content = msg.get("content")
            if content == "" or content is None:
                logger.debug(f"Fixing empty message at index {i}")
                messages[i]["content"] = self.EMPTY_CONTENT_REPLACEMENT
        return messages
    
    def _fix_assistant_ending(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Append user message if conversation ends with assistant."""
        if messages and messages[-1].get("role") == "assistant":
            logger.debug("Fixing conversation ending with assistant message")
            messages.append({
                "role": "user",
                "content": self.ASSISTANT_ENDING_APPEND,
            })
        return messages
