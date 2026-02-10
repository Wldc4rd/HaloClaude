"""
Agent Executor - Handles the agentic tool execution loop.

Sends requests to Claude, executes any tool calls, and loops
until Claude provides a final response.
"""

import json
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import anthropic

from halo.client import HaloClient
from context.injector import ContextInjector

if TYPE_CHECKING:
    from ninja.client import NinjaClient
    from mesh.client import MeshClient
    from cipp.client import CippClient

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
        context_injection_enabled: bool = True,
        context_cache_ttl: int = 300,
        sop_kb_search_term: Optional[str] = "SOP",
        sop_kb_filter_tag: Optional[str] = "ai-context",
        max_sop_articles: int = 10,
        max_sop_article_length: int = 2000,
        max_contract_doc_length: int = 5000,
        ninja_client: Optional["NinjaClient"] = None,
        mesh_client: Optional["MeshClient"] = None,
        cipp_client: Optional["CippClient"] = None,
    ):
        """
        Initialize the agent executor.

        Args:
            halo_client: Initialized Halo API client
            anthropic_api_key: Anthropic API key
            model: Claude model to use
            context_injection_enabled: Whether to pre-fetch and inject Halo context
            context_cache_ttl: Cache time-to-live for context in seconds
            sop_kb_search_term: Search term for SOP KB articles (None to disable)
            max_sop_articles: Maximum SOP articles to fetch
            max_sop_article_length: Max characters per SOP article content
            max_contract_doc_length: Max characters of extracted PDF text per contract
            ninja_client: Optional NinjaRMM client for device data tools
            mesh_client: Optional Mesh Email Security client for email log tools
            cipp_client: Optional CIPP client for M365 multi-tenant tools
        """
        self.halo_client = halo_client
        self.ninja_client = ninja_client
        self.mesh_client = mesh_client
        self.cipp_client = cipp_client
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.context_injector = ContextInjector(
            halo_client=halo_client,
            enabled=context_injection_enabled,
            cache_ttl=context_cache_ttl,
            sop_kb_search_term=sop_kb_search_term,
            sop_kb_filter_tag=sop_kb_filter_tag,
            max_sop_articles=max_sop_articles,
            max_sop_article_length=max_sop_article_length,
            max_contract_doc_length=max_contract_doc_length,
            ninja_client=ninja_client,
        )
    
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

        # Inject Halo context into system prompt
        system = await self.context_injector.inject_context(system)

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
            response = await self.client.messages.create(**request_kwargs)
            
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

            elif tool_name == "get_client_contracts":
                return await self.halo_client.get_client_contracts(
                    client_id=tool_input["client_id"],
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

            elif tool_name == "get_recurring_invoices":
                return await self.halo_client.get_recurring_invoices(
                    contract_id=tool_input.get("contract_id"),
                    client_id=tool_input.get("client_id"),
                )

            elif tool_name == "set_ticket_priority":
                return await self.halo_client.update_ticket(
                    ticket_id=tool_input["ticket_id"],
                    priority_id=tool_input["priority_id"],
                    sla_id=tool_input.get("sla_id"),
                )

            elif tool_name == "create_ticket":
                return await self.halo_client.create_ticket(
                    summary=tool_input["summary"],
                    client_id=tool_input["client_id"],
                    details=tool_input.get("details"),
                    user_id=tool_input.get("user_id"),
                    priority_id=tool_input.get("priority_id"),
                    ticket_type_id=tool_input.get("ticket_type_id"),
                    category_1=tool_input.get("category_1"),
                    category_2=tool_input.get("category_2"),
                )

            elif tool_name == "update_ticket":
                return await self.halo_client.update_ticket(
                    ticket_id=tool_input["ticket_id"],
                    summary=tool_input.get("summary"),
                    details=tool_input.get("details"),
                    priority_id=tool_input.get("priority_id"),
                    ticket_type_id=tool_input.get("ticket_type_id"),
                    category_1=tool_input.get("category_1"),
                    category_2=tool_input.get("category_2"),
                    agent_id=tool_input.get("agent_id"),
                    team_id=tool_input.get("team_id"),
                    status_id=tool_input.get("status_id"),
                )

            elif tool_name == "close_ticket":
                return await self.halo_client.close_ticket(
                    ticket_id=tool_input["ticket_id"],
                    note=tool_input.get("note"),
                )

            elif tool_name == "create_ticket_note":
                return await self.halo_client.create_ticket_note(
                    ticket_id=tool_input["ticket_id"],
                    note=tool_input["note"],
                    hiddenfromuser=tool_input.get("hiddenfromuser", True),
                    action_id=tool_input.get("action_id"),
                )

            elif tool_name == "list_tickets":
                kwargs = {
                    "client_id": tool_input.get("client_id"),
                    "open_only": tool_input.get("open_only", False),
                    "closed_only": tool_input.get("closed_only", False),
                    "agent_id": tool_input.get("agent_id"),
                    "asset_id": tool_input.get("asset_id"),
                    "count": tool_input.get("count", 25),
                    "order": "dateoccured",
                    "orderdesc": True,
                }
                opened_after = tool_input.get("opened_after")
                opened_before = tool_input.get("opened_before")
                if opened_after or opened_before:
                    kwargs["datesearch"] = "dateoccured"
                    kwargs["startdate"] = opened_after
                    kwargs["enddate"] = opened_before
                kwargs["lastupdatefromdate"] = tool_input.get("last_updated_after")
                kwargs["lastupdatetodate"] = tool_input.get("last_updated_before")
                return await self.halo_client.list_tickets(**kwargs)

            elif tool_name == "batch_close_tickets":
                return await self.halo_client.batch_close_tickets(
                    ticket_ids=tool_input["ticket_ids"],
                    note=tool_input.get("note"),
                )

            elif tool_name == "get_client_users":
                return await self.halo_client.get_client_users(
                    client_id=tool_input["client_id"],
                    include_active=tool_input.get("include_active", True),
                    include_inactive=tool_input.get("include_inactive", False),
                    search=tool_input.get("search"),
                    count=tool_input.get("count", 50),
                )

            elif tool_name == "search_assets":
                return await self.halo_client.search_assets(
                    search=tool_input.get("search"),
                    client_id=tool_input.get("client_id"),
                    count=tool_input.get("count", 50),
                )

            elif tool_name == "get_related_tickets":
                return await self.halo_client.get_related_tickets(
                    ticket_id=tool_input["ticket_id"],
                )

            # NinjaRMM tools
            elif tool_name == "ninja_get_device":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device(tool_input["device_id"])

            elif tool_name == "ninja_get_device_volumes":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_volumes(tool_input["device_id"])

            elif tool_name == "ninja_get_device_alerts":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_alerts(tool_input["device_id"])

            elif tool_name == "ninja_get_device_os_patches":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_os_patches(tool_input["device_id"])

            elif tool_name == "ninja_get_device_software":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_software(tool_input["device_id"])

            elif tool_name == "ninja_get_device_processors":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_processors(tool_input["device_id"])

            elif tool_name == "ninja_get_device_last_user":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_last_user(tool_input["device_id"])

            elif tool_name == "ninja_get_device_disk_drives":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_disk_drives(tool_input["device_id"])

            elif tool_name == "ninja_get_device_network_interfaces":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_network_interfaces(tool_input["device_id"])

            elif tool_name == "ninja_get_device_windows_services":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.get_device_windows_services(tool_input["device_id"])

            elif tool_name == "ninja_search_devices":
                if not self.ninja_client:
                    return {"error": "NinjaRMM integration is not enabled"}
                return await self.ninja_client.search_devices(
                    query=tool_input["query"],
                    limit=tool_input.get("limit", 25),
                )

            # Mesh Email Security tools
            elif tool_name == "mesh_search_email_logs":
                if not self.mesh_client:
                    return {"error": "Mesh Email Security integration is not enabled"}
                return await self.mesh_client.search_email_logs(
                    direction=tool_input.get("direction", "inbound"),
                    from_addr=tool_input.get("from_addr"),
                    to_addr=tool_input.get("to_addr"),
                    subject=tool_input.get("subject"),
                    status=tool_input.get("status"),
                    verdict=tool_input.get("verdict"),
                    start=tool_input.get("start"),
                    end=tool_input.get("end"),
                    sender_ip=tool_input.get("sender_ip"),
                    message_id=tool_input.get("message_id"),
                    size=tool_input.get("size", 50),
                )

            elif tool_name == "mesh_get_email_events":
                if not self.mesh_client:
                    return {"error": "Mesh Email Security integration is not enabled"}
                return await self.mesh_client.get_email_log_events(tool_input["queue_id"])

            elif tool_name == "mesh_get_email_by_id":
                if not self.mesh_client:
                    return {"error": "Mesh Email Security integration is not enabled"}
                return await self.mesh_client.get_email_by_message_id(
                    message_id=tool_input["message_id"],
                    direction=tool_input.get("direction", "inbound"),
                )

            elif tool_name == "mesh_search_customers":
                if not self.mesh_client:
                    return {"error": "Mesh Email Security integration is not enabled"}
                return await self.mesh_client.search_customers(
                    filter_term=tool_input["filter_term"],
                )

            # CIPP tools
            elif tool_name == "cipp_list_tenants":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_tenants()

            elif tool_name == "cipp_list_users":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_users(tool_input["tenant_filter"])

            elif tool_name == "cipp_list_groups":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_groups(tool_input["tenant_filter"])

            elif tool_name == "cipp_list_user_groups":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_user_groups(
                    tool_input["tenant_filter"], tool_input["user_id"],
                )

            elif tool_name == "cipp_list_mailboxes":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_mailboxes(tool_input["tenant_filter"])

            elif tool_name == "cipp_list_mailbox_permissions":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_mailbox_permissions(
                    tool_input["tenant_filter"], tool_input["user_id"],
                )

            elif tool_name == "cipp_list_mailbox_rules":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_mailbox_rules(
                    tool_input["tenant_filter"], tool_input["user_id"],
                )

            elif tool_name == "cipp_list_devices":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_devices(tool_input["tenant_filter"])

            elif tool_name == "cipp_list_licenses":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_licenses(tool_input["tenant_filter"])

            elif tool_name == "cipp_list_sign_ins":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_sign_ins(tool_input["tenant_filter"])

            elif tool_name == "cipp_list_defender_state":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_defender_state(tool_input["tenant_filter"])

            elif tool_name == "cipp_list_conditional_access_policies":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.list_conditional_access_policies(
                    tool_input["tenant_filter"],
                )

            elif tool_name == "cipp_reset_password":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.reset_password(
                    tool_input["tenant_filter"], tool_input["user_id"],
                )

            elif tool_name == "cipp_disable_user":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.disable_user(
                    tool_input["tenant_filter"], tool_input["user_id"],
                )

            elif tool_name == "cipp_device_action":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.device_action(
                    tool_input["tenant_filter"],
                    tool_input["device_id"],
                    tool_input["action"],
                )

            elif tool_name == "cipp_edit_mailbox_permissions":
                if not self.cipp_client:
                    return {"error": "CIPP integration is not enabled"}
                return await self.cipp_client.edit_mailbox_permissions(
                    tool_input["tenant_filter"],
                    tool_input["user_id"],
                    tool_input["permissions"],
                )

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e)}
