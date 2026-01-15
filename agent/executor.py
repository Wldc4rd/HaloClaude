"""
Agent Executor - Handles the agentic tool execution loop.

Sends requests to Claude, executes any tool calls, and loops
until Claude provides a final response.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import anthropic

from halo.client import HaloClient

logger = logging.getLogger(__name__)

# Maximum number of tool execution rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 10


class AgentExecutor:
    """Executes the agent loop with tool calling."""
    
    def __init__(
        self,
        halo_client: HaloClient,
        anthropic_api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
    ):
        """
        Initialize the agent executor.
        
        Args:
            halo_client: Initialized Halo API client
            anthropic_api_key: Anthropic API key
            model: Claude model to use
        """
        self.halo_client = halo_client
        self.model = model
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
    
    async def run(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the agent loop until a final response is generated.
        
        Args:
            messages: Conversation messages
            tools: Tool definitions (optional)
            system: System prompt (optional, extracted from messages if not provided)
            
        Returns:
            Final Claude response
        """
        # Extract system message if present
        if system is None:
            messages, system = self._extract_system(messages)
        
        current_messages = list(messages)
        tool_round = 0
        
        while tool_round < MAX_TOOL_ROUNDS:
            tool_round += 1
            logger.debug(f"Agent round {tool_round}")
            
            # Build request kwargs
            request_kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": current_messages,
            }
            
            if system:
                request_kwargs["system"] = system
            
            if tools:
                request_kwargs["tools"] = tools
            
            # Call Claude
            response = self.client.messages.create(**request_kwargs)
            
            logger.debug(f"Claude response stop_reason: {response.stop_reason}")
            
            # Check if we need to execute tools
            if response.stop_reason == "tool_use":
                # Extract tool calls
                tool_calls = [
                    block for block in response.content
                    if block.type == "tool_use"
                ]
                
                # Add assistant response to messages
                current_messages.append({
                    "role": "assistant",
                    "content": [self._block_to_dict(b) for b in response.content],
                })
                
                # Execute tools and collect results
                tool_results = []
                for tool_call in tool_calls:
                    result = await self._execute_tool(
                        tool_call.name,
                        tool_call.input,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                    })
                
                # Add tool results to messages
                current_messages.append({
                    "role": "user",
                    "content": tool_results,
                })
                
            else:
                # No more tool calls, return final response
                return self._response_to_dict(response)
        
        # Max rounds exceeded
        logger.warning(f"Max tool rounds ({MAX_TOOL_ROUNDS}) exceeded")
        return self._response_to_dict(response)
    
    def _extract_system(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Extract system message from message list."""
        system = None
        filtered = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content", "")
            else:
                filtered.append(msg)
        
        return filtered, system
    
    def _block_to_dict(self, block) -> Dict[str, Any]:
        """Convert a content block to a dictionary."""
        if block.type == "text":
            return {"type": "text", "text": block.text}
        elif block.type == "tool_use":
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        else:
            return {"type": block.type}
    
    def _response_to_dict(self, response) -> Dict[str, Any]:
        """Convert Claude response to dictionary format."""
        return {
            "id": response.id,
            "type": response.type,
            "role": response.role,
            "content": [self._block_to_dict(b) for b in response.content],
            "model": response.model,
            "stop_reason": response.stop_reason,
            "stop_sequence": response.stop_sequence,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
    
    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Any:
        """
        Execute a tool and return its result.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters
            
        Returns:
            Tool execution result
        """
        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
        
        try:
            if tool_name == "get_ticket":
                return await self.halo_client.get_ticket(tool_input["ticket_id"])
            
            elif tool_name == "get_user":
                return await self.halo_client.get_user(tool_input["user_id"])
            
            elif tool_name == "get_user_tickets":
                return await self.halo_client.get_user_tickets(
                    user_id=tool_input["user_id"],
                    count=tool_input.get("count", 10),
                    open_only=tool_input.get("open_only", False),
                )
            
            elif tool_name == "get_client":
                return await self.halo_client.get_client(tool_input["client_id"])
            
            elif tool_name == "get_client_tickets":
                return await self.halo_client.get_client_tickets(
                    client_id=tool_input["client_id"],
                    count=tool_input.get("count", 10),
                    open_only=tool_input.get("open_only", False),
                )
            
            elif tool_name == "get_asset":
                return await self.halo_client.get_asset(tool_input["asset_id"])
            
            elif tool_name == "search_tickets":
                return await self.halo_client.search_tickets(
                    query=tool_input["query"],
                    count=tool_input.get("count", 10),
                    client_id=tool_input.get("client_id"),
                    user_id=tool_input.get("user_id"),
                )
            
            elif tool_name == "search_kb":
                return await self.halo_client.search_kb(
                    query=tool_input["query"],
                    count=tool_input.get("count", 5),
                )
            
            elif tool_name == "get_kb_article":
                return await self.halo_client.get_kb_article(tool_input["article_id"])
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e)}
