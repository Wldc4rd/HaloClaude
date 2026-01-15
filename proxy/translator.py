"""
Azure OpenAI ↔ Claude API Translator

Translates between Azure OpenAI API format and Claude's Messages API format.
"""

import uuid
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class AzureOpenAITranslator:
    """Translates between Azure OpenAI and Claude API formats."""
    
    def to_claude_messages(
        self, azure_messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert Azure OpenAI messages to Claude format.
        
        Azure OpenAI and Claude use similar message formats, but there
        are some differences in how system messages are handled.
        
        Args:
            azure_messages: Messages in Azure OpenAI format
            
        Returns:
            Messages in Claude format
        """
        claude_messages = []
        system_content = None
        
        for msg in azure_messages:
            role = msg.get("role")
            content = msg.get("content", "")
            
            if role == "system":
                # Claude handles system messages separately
                system_content = content
            else:
                claude_messages.append({
                    "role": role,
                    "content": content,
                })
        
        return claude_messages, system_content
    
    def to_azure_openai(
        self,
        claude_response: Dict[str, Any],
        model: str = "claude-sonnet-4-5-20250929"
    ) -> Dict[str, Any]:
        """
        Convert Claude response to Azure OpenAI format.
        
        Args:
            claude_response: Response from Claude API
            model: Model name to include in response
            
        Returns:
            Response in Azure OpenAI format
        """
        # Extract content from Claude response
        content = self._extract_content(claude_response)
        
        # Calculate tokens
        input_tokens = claude_response.get("usage", {}).get("input_tokens", 0)
        output_tokens = claude_response.get("usage", {}).get("output_tokens", 0)
        
        # Build Azure OpenAI format response
        return {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "created": int(time.time()),
            "model": model,
            "object": "chat.completion",
            "choices": [
                {
                    "finish_reason": self._map_stop_reason(
                        claude_response.get("stop_reason")
                    ),
                    "index": 0,
                    "message": {
                        "content": content,
                        "role": "assistant",
                    }
                }
            ],
            "usage": {
                "completion_tokens": output_tokens,
                "prompt_tokens": input_tokens,
                "total_tokens": input_tokens + output_tokens,
                "completion_tokens_details": {
                    "text_tokens": output_tokens,
                },
                "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "cache_creation_tokens": 0,
                    "cache_creation_token_details": {
                        "ephemeral_5m_input_tokens": 0,
                        "ephemeral_1h_input_tokens": 0,
                    }
                },
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        }
    
    def _extract_content(self, claude_response: Dict[str, Any]) -> str:
        """Extract text content from Claude response."""
        content_blocks = claude_response.get("content", [])
        
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        
        return "".join(text_parts)
    
    def _map_stop_reason(self, claude_stop_reason: str) -> str:
        """Map Claude stop reason to OpenAI finish reason."""
        mapping = {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls",
        }
        return mapping.get(claude_stop_reason, "stop")
