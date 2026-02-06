"""
Ticket Triage Pipeline

Sequential multi-stage pipeline that triages a new ticket:
1. Triage Agent - classifies client/contract situation
2a. Sales Path - creates opportunity if no contract/prepaid time
2b. Contract Enrichment - generates contract notes if missing
3. Technical Triage - assigns technician and writes analysis note
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import anthropic

from halo.client import HaloClient
from context.fetcher import ContextFetcher, ContextData
from context.formatter import ContextFormatter
from .prompts import (
    TRIAGE_SYSTEM_PROMPT,
    TECHNICAL_TRIAGE_SYSTEM_PROMPT,
    CONTRACT_SUMMARY_PROMPT,
)

logger = logging.getLogger(__name__)

# Agent assignment mapping
JUSTIN_TOP_LEVEL_ID = 14
JUSTIN_AGENT_ID = 51
CHARLIE_AGENT_ID = 3


@dataclass
class TriageResult:
    """Output of Stage 1 triage classification."""

    client_type: str  # "managed_services", "break_fix", "no_contract"
    has_active_contract: bool
    has_prepaid_time: bool
    prepaid_balance: float
    contract_ids: List[int] = field(default_factory=list)
    work_covered_by_managed: bool = False
    route: str = ""  # "sales" or "technical"
    reasoning: str = ""


async def run_triage_pipeline(
    ticket_id: int,
    halo_client: HaloClient,
    ninja_client: Optional[Any],
    anthropic_api_key: str,
    model: str,
    sop_kb_search_term: Optional[str] = "SOP",
    sop_kb_filter_tag: Optional[str] = "ai-context",
    max_sop_articles: int = 10,
    max_sop_article_length: int = 2000,
    max_contract_doc_length: int = 5000,
) -> Dict[str, Any]:
    """
    Run the full triage pipeline for a ticket.

    Returns a summary dict of what happened (for logging).
    """
    result: Dict[str, Any] = {
        "ticket_id": ticket_id,
        "stages_completed": [],
        "errors": [],
    }

    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    # --- Fetch context (reuse existing ContextFetcher) ---
    fetcher = ContextFetcher(
        halo_client=halo_client,
        sop_kb_search_term=sop_kb_search_term,
        sop_kb_filter_tag=sop_kb_filter_tag,
        max_sop_articles=max_sop_articles,
        max_contract_doc_length=max_contract_doc_length,
        ninja_client=ninja_client,
    )
    formatter = ContextFormatter(
        max_sop_article_length=max_sop_article_length,
        max_contract_doc_length=max_contract_doc_length,
    )

    logger.info(f"Triage pipeline starting for ticket {ticket_id}")

    context = await fetcher.fetch_full_context(ticket_id)
    if not context.ticket:
        result["errors"].append(f"Could not fetch ticket {ticket_id}")
        logger.error(f"Triage pipeline aborted: could not fetch ticket {ticket_id}")
        return result

    formatted_context = formatter.format(context)

    # ========================================
    # STAGE 1: Triage Classification
    # ========================================
    try:
        triage = await _stage1_triage(client, model, context, formatted_context)
        result["stages_completed"].append("triage")
        result["triage"] = {
            "client_type": triage.client_type,
            "has_active_contract": triage.has_active_contract,
            "has_prepaid_time": triage.has_prepaid_time,
            "prepaid_balance": triage.prepaid_balance,
            "route": triage.route,
            "reasoning": triage.reasoning,
        }
    except Exception as e:
        logger.exception(f"Stage 1 triage failed for ticket {ticket_id}: {e}")
        result["errors"].append(f"Triage failed: {e}")
        # Write failure note to ticket so the team knows
        try:
            await halo_client.create_ticket_note(
                ticket_id=ticket_id,
                note=f"<b>Triage Pipeline Error</b><br>Stage 1 classification failed: {e}",
                hiddenfromuser=True,
            )
        except Exception:
            pass
        return result

    # ========================================
    # STAGE 2b: Contract Enrichment (if needed)
    # ========================================
    # Determine which contracts need notes by inspecting the actual data
    # (don't rely on Claude's assessment — it's unreliable for this check)
    contracts_needing_notes = _find_contracts_needing_notes(context.contracts)
    if contracts_needing_notes:
        try:
            await _stage2b_enrich_contracts(
                client, model, halo_client, context, contracts_needing_notes
            )
            result["stages_completed"].append("contract_enrichment")
        except Exception as e:
            logger.warning(f"Contract enrichment failed: {e}")
            result["errors"].append(f"Contract enrichment failed: {e}")
            # Non-fatal, continue pipeline

    # ========================================
    # STAGE 2c: Asset Auto-Assignment
    # ========================================
    if not context.assets:
        try:
            matched_asset = await _stage2c_auto_assign_asset(
                halo_client, ninja_client, ticket_id, context, fetcher
            )
            if matched_asset:
                result["stages_completed"].append("asset_auto_assign")
                result["auto_assigned_asset"] = {
                    "id": matched_asset.get("id"),
                    "name": (
                        matched_asset.get("inventory_number")
                        or matched_asset.get("key_field", "")
                    ),
                }
                # Re-format context so Stage 3 sees the device data
                formatted_context = formatter.format(context)
        except Exception as e:
            logger.warning(f"Asset auto-assignment failed for ticket {ticket_id}: {e}")
            result["errors"].append(f"Asset auto-assignment failed: {e}")
            # Non-fatal, continue pipeline

    # ========================================
    # STAGE 2a: Sales Path
    # ========================================
    if triage.route == "sales":
        try:
            await _stage2a_sales_path(halo_client, ticket_id, context, triage)
            result["stages_completed"].append("sales_path")
            result["route"] = "sales"
        except Exception as e:
            logger.exception(f"Sales path failed for ticket {ticket_id}: {e}")
            result["errors"].append(f"Sales path failed: {e}")
        logger.info(f"Triage pipeline complete for ticket {ticket_id}: {result}")
        return result

    # ========================================
    # STAGE 3: Technical Triage
    # ========================================
    if triage.route == "technical":
        try:
            await _stage3_technical_triage(
                client, model, halo_client, ninja_client,
                ticket_id, context, formatted_context,
            )
            result["stages_completed"].append("technical_triage")
            result["route"] = "technical"
        except Exception as e:
            logger.exception(f"Technical triage failed for ticket {ticket_id}: {e}")
            result["errors"].append(f"Technical triage failed: {e}")

    logger.info(f"Triage pipeline complete for ticket {ticket_id}: {result}")
    return result


# =============================================================================
# Stage Implementations
# =============================================================================


async def _stage1_triage(
    client: anthropic.AsyncAnthropic,
    model: str,
    context: ContextData,
    formatted_context: str,
) -> TriageResult:
    """
    Stage 1: Classify client/contract situation.

    Calls Claude with the full context and asks for a structured JSON
    classification. Python then applies routing rules.
    """
    system = TRIAGE_SYSTEM_PROMPT + "\n\n" + formatted_context

    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{
            "role": "user",
            "content": (
                "Analyze this ticket's client, contracts, and prepaid balances. "
                "Respond with ONLY a JSON object matching the format described "
                "in the system prompt."
            ),
        }],
    )

    # Parse Claude's JSON response
    text = response.content[0].text.strip()
    # Handle potential markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(text)

    triage = TriageResult(
        client_type=data.get("client_type", "no_contract"),
        has_active_contract=data.get("has_active_contract", False),
        has_prepaid_time=data.get("has_prepaid_time", False),
        prepaid_balance=float(data.get("prepaid_balance", 0.0)),
        contract_ids=data.get("contract_ids", []),
        work_covered_by_managed=data.get("work_covered_by_managed", False),
        reasoning=data.get("reasoning", ""),
    )

    # Determine route based on decision logic (Python, not Claude)
    if not triage.has_active_contract:
        triage.route = "sales"
    elif triage.client_type == "break_fix" and not triage.has_prepaid_time:
        triage.route = "sales"
    elif triage.client_type == "managed_services" and not triage.has_prepaid_time:
        if not triage.work_covered_by_managed:
            triage.route = "sales"
        else:
            triage.route = "technical"
    else:
        triage.route = "technical"

    logger.info(
        f"Triage result: type={triage.client_type}, "
        f"active_contract={triage.has_active_contract}, "
        f"prepaid={triage.has_prepaid_time} ({triage.prepaid_balance}h), "
        f"route={triage.route}, "
        f"reasoning={triage.reasoning}"
    )

    return triage


async def _stage2a_sales_path(
    halo_client: HaloClient,
    ticket_id: int,
    context: ContextData,
    triage: TriageResult,
) -> None:
    """Stage 2a: Create opportunity and add private note to ticket."""
    client_id = context.ticket.get("client_id")
    if isinstance(client_id, dict):
        client_id = client_id.get("id")

    client_name = ""
    if context.client:
        client_name = context.client.get("name", "")

    ticket_summary = context.ticket.get("summary", "")

    # Create opportunity in Halo
    opp = await halo_client.create_opportunity(
        summary=f"Sales follow-up: {ticket_summary}",
        client_id=client_id,
        details=(
            f"Auto-generated from ticket #{ticket_id}.\n\n"
            f"Reason: {triage.reasoning}\n\n"
            f"Client: {client_name}\n"
            f"Client type: {triage.client_type}\n"
            f"Active contract: {triage.has_active_contract}\n"
            f"Prepaid balance: {triage.prepaid_balance}h"
        ),
    )

    # Halo POST returns a list; get ID from first element
    opp_id = "unknown"
    if isinstance(opp, list) and opp:
        opp_id = opp[0].get("id", "unknown")
    elif isinstance(opp, dict):
        opp_id = opp.get("id", "unknown")

    # Add private note to ticket
    note_text = (
        f"<b>Triage Pipeline - Sales Path</b><br><br>"
        f"This ticket requires sales attention before technical work can begin.<br><br>"
        f"<b>Reason:</b> {triage.reasoning}<br>"
        f"<b>Client type:</b> {triage.client_type}<br>"
        f"<b>Active contract:</b> {'Yes' if triage.has_active_contract else 'No'}<br>"
        f"<b>Prepaid balance:</b> {triage.prepaid_balance}h<br><br>"
        f"<b>Opportunity created:</b> #{opp_id}"
    )

    await halo_client.create_ticket_note(
        ticket_id=ticket_id,
        note=note_text,
        hiddenfromuser=True,
    )

    logger.info(
        f"Sales path complete for ticket {ticket_id}: "
        f"opportunity #{opp_id} created"
    )


async def _stage2c_auto_assign_asset(
    halo_client: HaloClient,
    ninja_client: Optional[Any],
    ticket_id: int,
    context: ContextData,
    fetcher: ContextFetcher,
) -> Optional[Dict[str, Any]]:
    """
    Stage 2c: Auto-identify and link user's workstation to the ticket.

    After linking, refreshes context.assets and context.ninja_devices
    so downstream stages have device data.
    """
    from .asset_matcher import find_and_link_workstation

    # Extract user info
    user_id = None
    user_name = ""
    user_email = None
    if context.user:
        user_id = context.user.get("id")
        user_name = context.user.get("name", "")
        user_email = context.user.get("emailaddress")

    if not user_id:
        logger.info(f"Asset auto-assign skipped: no user on ticket {ticket_id}")
        return None

    # Extract client_id
    client_id = None
    if context.client:
        client_id = context.client.get("id")
    if not client_id:
        logger.info(f"Asset auto-assign skipped: no client on ticket {ticket_id}")
        return None

    matched_asset = await find_and_link_workstation(
        ticket_id=ticket_id,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        client_id=client_id,
        halo_client=halo_client,
        ninja_client=ninja_client,
    )

    if matched_asset:
        # Update context so Stage 3 has the asset data
        context.assets.append(matched_asset)

        # Fetch NinjaRMM device data if the asset has a ninjarmm_id
        if fetcher.ninja_client and matched_asset.get("ninjarmm_id"):
            ninja_devices = await fetcher._fetch_ninja_devices([matched_asset])
            context.ninja_devices.update(ninja_devices)

        logger.info(
            f"Asset auto-assign complete: linked asset "
            f"{matched_asset.get('id')} to ticket {ticket_id}"
        )

    return matched_asset


async def _stage2b_enrich_contracts(
    client: anthropic.AsyncAnthropic,
    model: str,
    halo_client: HaloClient,
    context: ContextData,
    contract_ids: List[int],
) -> None:
    """Stage 2b: Fetch contract PDFs, generate summaries, and save as notes."""
    # Build lookup by ID from context
    contract_by_id: Dict[int, Dict[str, Any]] = {
        c["id"]: c for c in context.contracts if c.get("id")
    }

    contracts_to_enrich = [
        contract_by_id[cid] for cid in contract_ids if cid in contract_by_id
    ]

    logger.info(
        f"Contract enrichment: ids_to_enrich={contract_ids}, "
        f"matched={[c.get('id') for c in contracts_to_enrich]}"
    )
    contract_doc_texts: Dict[int, str] = {}

    # Fetch PDF attachments for each contract
    for contract in contracts_to_enrich:
        cid = contract.get("id")
        if not cid:
            continue
        try:
            attachments = await halo_client.get_contract_attachments(cid)
            if not attachments:
                logger.debug(f"No attachments for contract {cid}")
                continue

            # Find first PDF attachment
            pdf_attach = None
            for att in attachments:
                if att.get("filename", "").lower().endswith(".pdf"):
                    pdf_attach = att
                    break
            if not pdf_attach:
                pdf_attach = attachments[0]

            pdf_bytes = await halo_client.get_attachment_bytes(pdf_attach["id"])
            if pdf_bytes:
                from context.fetcher import ContextFetcher
                text = ContextFetcher._extract_pdf_text(pdf_bytes)
                if text:
                    contract_doc_texts[cid] = text
                    logger.info(
                        f"Extracted {len(text)} chars from contract {cid} PDF "
                        f"for enrichment"
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch PDF for contract {cid}: {e}")

    # Generate and save summaries
    for contract in contracts_to_enrich:
        cid = contract.get("id")
        if not cid:
            continue

        contract_text = _format_contract_for_summary(
            contract, contract_doc_texts.get(cid, "")
        )

        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=CONTRACT_SUMMARY_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Generate a concise summary for this contract:\n\n{contract_text}",
            }],
        )

        summary = response.content[0].text.strip()

        await halo_client.update_contract(contract_id=cid, note=summary)
        logger.info(f"Updated contract {cid} notes with AI-generated summary")


async def _stage3_technical_triage(
    client: anthropic.AsyncAnthropic,
    model: str,
    halo_client: HaloClient,
    ninja_client: Optional[Any],
    ticket_id: int,
    context: ContextData,
    formatted_context: str,
) -> None:
    """Stage 3: Assign technician and write technical analysis note."""
    # Determine agent assignment based on client's top_level_id
    top_level_id = None
    if context.client:
        top_level_id = context.client.get("top_level_id")

    if top_level_id == JUSTIN_TOP_LEVEL_ID:
        agent_id = JUSTIN_AGENT_ID
        agent_name = "Justin"
    else:
        agent_id = CHARLIE_AGENT_ID
        agent_name = "Charlie"

    # Assign ticket to the correct technician
    await halo_client.update_ticket(ticket_id=ticket_id, agent_id=agent_id)
    logger.info(f"Assigned ticket {ticket_id} to {agent_name} (agent_id={agent_id})")

    # Build tool list (read-only tools only)
    tools = _get_triage_tools()

    system = TECHNICAL_TRIAGE_SYSTEM_PROMPT + "\n\n" + formatted_context

    messages: List[Dict[str, Any]] = [{
        "role": "user",
        "content": (
            "Perform a thorough technical analysis of this ticket. "
            "Use tools to search for similar past tickets, relevant KB articles, "
            "and device data if applicable. Then provide your analysis as a "
            "structured note following the format in your instructions."
        ),
    }]

    # Agentic tool loop (same pattern as AgentExecutor.run)
    max_rounds = 10
    final_text = ""

    for _round in range(max_rounds):
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=tools,
        )

        if response.stop_reason == "tool_use":
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            messages.append({
                "role": "assistant",
                "content": [_block_to_dict(b) for b in response.content],
            })

            tool_results = []
            for tc in tool_calls:
                tool_result = await _execute_triage_tool(
                    tc.name, tc.input, halo_client, ninja_client,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": (
                        json.dumps(tool_result)
                        if isinstance(tool_result, (dict, list))
                        else str(tool_result)
                    ),
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Extract final text
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            break

    if not final_text:
        final_text = "Technical analysis could not be completed."

    # Write analysis as private note
    # Convert newlines to <br> for HTML rendering in Halo
    note_html = (
        f"<b>AI Technical Triage Analysis</b><br>"
        f"<b>Assigned to:</b> {agent_name}<br><br>"
        f"{final_text.replace(chr(10), '<br>')}"
    )

    await halo_client.create_ticket_note(
        ticket_id=ticket_id,
        note=note_html,
        hiddenfromuser=True,
    )

    logger.info(f"Technical triage complete for ticket {ticket_id}")


# =============================================================================
# Helper Functions
# =============================================================================


def _block_to_dict(block) -> Dict[str, Any]:
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
    return {"type": block.type}


def _find_contracts_needing_notes(contracts: List[Dict[str, Any]]) -> List[int]:
    """
    Check which active contracts have empty or very sparse notes.

    Returns list of contract IDs that need AI-generated summaries.
    """
    ids = []
    for c in contracts:
        # Only enrich active contracts (started and not expired)
        started = c.get("started", False)
        expired = c.get("expired", False)
        if not started or expired:
            continue

        cid = c.get("id")
        if not cid:
            continue

        note = c.get("note") or c.get("Notes") or ""
        note = str(note).strip()
        if len(note) < 50:
            ids.append(cid)
            logger.info(
                f"Contract {cid} (ref={c.get('ref')}) needs notes "
                f"(current length={len(note)})"
            )

    return ids


def _format_contract_for_summary(
    contract: Dict[str, Any],
    doc_text: str,
) -> str:
    """Format a single contract's data for summary generation."""
    lines = [
        f"Reference: {contract.get('ref', '?')}",
        f"Type: {contract.get('contracttype_name', '?')}",
        f"SLA: {contract.get('sla_name', '?')}",
        f"Start: {contract.get('start_date', '?')}",
        f"End: {contract.get('end_date', '?')}",
        f"Prepaid Total: {contract.get('contract_prepaytotal', 0)}",
        f"Prepaid Used: {contract.get('contract_prepayused', 0)}",
        f"Prepaid Balance: {contract.get('contract_prepaybalance', 0)}",
    ]
    if doc_text:
        lines.append(f"\nContract Document Text:\n{doc_text[:10000]}")
    return "\n".join(lines)


async def _execute_triage_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    halo_client: HaloClient,
    ninja_client: Optional[Any],
) -> Any:
    """
    Execute a read-only tool for technical triage analysis.

    Only read-only tools are available here to prevent the analysis
    agent from modifying state.
    """
    try:
        # Halo read-only tools
        if tool_name == "get_ticket":
            return await halo_client.get_ticket(tool_input["ticket_id"])
        elif tool_name == "get_user":
            return await halo_client.get_user(tool_input["user_id"])
        elif tool_name == "get_client":
            return await halo_client.get_client(tool_input["client_id"])
        elif tool_name == "get_asset":
            return await halo_client.get_asset(tool_input["asset_id"])
        elif tool_name == "search_tickets":
            return await halo_client.search_tickets(
                query=tool_input["query"],
                count=tool_input.get("count", 10),
                client_id=tool_input.get("client_id"),
                user_id=tool_input.get("user_id"),
            )
        elif tool_name == "search_kb":
            return await halo_client.search_kb(
                query=tool_input["query"],
                count=tool_input.get("count", 5),
            )
        elif tool_name == "get_kb_article":
            return await halo_client.get_kb_article(tool_input["article_id"])
        elif tool_name == "get_client_contracts":
            return await halo_client.get_client_contracts(tool_input["client_id"])
        # NinjaRMM read-only tools
        elif tool_name.startswith("ninja_") and ninja_client:
            method_map = {
                "ninja_get_device": lambda: ninja_client.get_device(tool_input["device_id"]),
                "ninja_get_device_volumes": lambda: ninja_client.get_device_volumes(tool_input["device_id"]),
                "ninja_get_device_alerts": lambda: ninja_client.get_device_alerts(tool_input["device_id"]),
                "ninja_get_device_os_patches": lambda: ninja_client.get_device_os_patches(tool_input["device_id"]),
                "ninja_get_device_software": lambda: ninja_client.get_device_software(tool_input["device_id"]),
                "ninja_get_device_processors": lambda: ninja_client.get_device_processors(tool_input["device_id"]),
                "ninja_get_device_last_user": lambda: ninja_client.get_device_last_user(tool_input["device_id"]),
                "ninja_get_device_disk_drives": lambda: ninja_client.get_device_disk_drives(tool_input["device_id"]),
                "ninja_get_device_network_interfaces": lambda: ninja_client.get_device_network_interfaces(tool_input["device_id"]),
                "ninja_get_device_windows_services": lambda: ninja_client.get_device_windows_services(tool_input["device_id"]),
            }
            handler = method_map.get(tool_name)
            if handler:
                return await handler()
            return {"error": f"Unknown ninja tool: {tool_name}"}
        else:
            return {"error": f"Tool not available in triage: {tool_name}"}
    except Exception as e:
        logger.warning(f"Triage tool {tool_name} failed: {e}")
        return {"error": str(e)}


def _get_triage_tools() -> List[Dict[str, Any]]:
    """
    Get the read-only tool definitions for technical triage.

    This is a subset of the full tool list — only tools that read data.
    Write operations (create/update/close ticket, create note) are excluded.
    """
    from halo.tools import get_halo_tools
    from ninja.tools import get_ninja_tools

    # Whitelist of read-only Halo tool names
    read_only_halo = {
        "get_ticket", "get_user", "get_client", "get_asset",
        "search_tickets", "search_kb", "get_kb_article",
        "get_client_contracts",
    }

    tools = [t for t in get_halo_tools() if t["name"] in read_only_halo]

    # Add all NinjaRMM tools (all read-only)
    try:
        tools.extend(get_ninja_tools())
    except ImportError:
        pass

    return tools
