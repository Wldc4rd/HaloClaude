"""
Ticket Triage Pipeline

Sequential multi-stage pipeline that triages a new ticket:
0. User/Client Resolution - identifies and links user/client for unlinked tickets
1. Triage Agent - classifies client/contract situation
2a. Sales Path - creates opportunity if no contract/prepaid time
2b. Contract Enrichment - generates contract notes if missing
2c. Asset Auto-Assignment - links user's workstation to ticket
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
    mesh_client: Optional[Any] = None,
    cipp_client: Optional[Any] = None,
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
    # STAGE 0: User/Client Resolution
    # ========================================
    from .user_matcher import is_system_user
    needs_user_resolution = (
        not context.user
        or not context.client
        or is_system_user(context.user)
    )
    if needs_user_resolution:
        try:
            resolution = await _stage0_resolve_user_or_client(
                halo_client, ticket_id, context, fetcher, formatter,
                ninja_client=ninja_client,
                anthropic_client=client,
                model=model,
            )
            if resolution:
                result["stages_completed"].append("user_resolution")
                if resolution.get("user"):
                    result["resolved_user"] = {
                        "id": resolution["user"].get("id"),
                        "name": resolution["user"].get("name"),
                    }
                if resolution.get("client_id"):
                    result["resolved_client_id"] = resolution["client_id"]
                if resolution.get("asset"):
                    result["resolved_asset"] = {
                        "id": resolution["asset"].get("id"),
                        "name": (
                            resolution["asset"].get("inventory_number")
                            or resolution["asset"].get("key_field", "")
                        ),
                    }
                # Context was re-fetched inside the stage function
                formatted_context = formatter.format(context)
        except Exception as e:
            logger.warning(f"User/client resolution failed for ticket {ticket_id}: {e}")
            result["errors"].append(f"User/client resolution failed: {e}")
            # Non-fatal, continue pipeline

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
    # Check all active contracts — Stage 2b will evaluate note quality
    contracts_to_check = _find_active_contracts(context.contracts)
    if contracts_to_check:
        try:
            await _stage2b_enrich_contracts(
                client, model, halo_client, context, contracts_to_check
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
                halo_client, ninja_client, ticket_id, context, fetcher,
                anthropic_client=client, model=model,
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
                client, model, halo_client, ninja_client, mesh_client,
                cipp_client, ticket_id, context, formatted_context, triage,
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


async def _stage0_resolve_user_or_client(
    halo_client: HaloClient,
    ticket_id: int,
    context: ContextData,
    fetcher: ContextFetcher,
    formatter: ContextFormatter,
    ninja_client: Optional[Any] = None,
    anthropic_client: Optional[Any] = None,
    model: str = "claude-sonnet-4-5-20250929",
) -> Optional[Dict[str, Any]]:
    """
    Stage 0: Identify and link user/client for unlinked tickets.

    Parses ticket content for email addresses and device hostnames,
    searches Halo for matches, and links the ticket. After linking,
    re-fetches the full context so downstream stages have correct data.
    """
    from .user_matcher import find_and_link_user_or_client

    resolution = await find_and_link_user_or_client(
        ticket_id=ticket_id,
        ticket=context.ticket,
        actions=context.actions,
        halo_client=halo_client,
        ninja_client=ninja_client,
        anthropic_client=anthropic_client,
        model=model,
    )

    if not resolution:
        return None

    # Re-fetch full context now that user/client are linked
    logger.info(f"Re-fetching context for ticket {ticket_id} after user/client resolution")
    new_context = await fetcher.fetch_full_context(ticket_id)

    # Update the context object in-place so the caller sees the changes
    context.ticket = new_context.ticket
    context.actions = new_context.actions
    context.user = new_context.user
    context.client = new_context.client
    context.assets = new_context.assets
    context.contracts = new_context.contracts
    context.contract_doc_texts = new_context.contract_doc_texts
    context.sop_articles = new_context.sop_articles
    context.ninja_devices = new_context.ninja_devices
    context.related_tickets = new_context.related_tickets
    context.errors = new_context.errors

    return resolution


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
    # Sales path: only for clients with NO active contract at all.
    # Clients with an active contract always go to technical — even if
    # prepaid time is exhausted, purchasing more credits is handled in
    # the support ticket, not via a separate sales opportunity.
    if not triage.has_active_contract:
        triage.route = "sales"
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
    anthropic_client: Optional[Any] = None,
    model: str = "claude-sonnet-4-5-20250929",
) -> Optional[Dict[str, Any]]:
    """
    Stage 2c: Auto-identify and link a workstation to the ticket.

    Strategies (in order):
      1. User-based matching (assigned assets, NinjaRMM last user, name match)
      2. Hostname from ticket text → Halo/NinjaRMM search
      3. Broad all-caps tokens → NinjaRMM device search
      4. AI hostname extraction → Halo/NinjaRMM search

    After linking, refreshes context.assets and context.ninja_devices
    so downstream stages have device data.
    """
    from .asset_matcher import find_and_link_workstation
    from .user_matcher import (
        _collect_ticket_text,
        _extract_hostnames,
        _extract_allcaps_tokens,
        _try_hostname_match,
        _try_ninja_hostname_search,
        _ai_extract_hostname,
    )

    matched_asset = None

    # === Strategy 1: User-based workstation matching ===
    user_id = None
    user_name = ""
    user_email = None
    if context.user:
        user_id = context.user.get("id")
        user_name = context.user.get("name", "")
        user_email = context.user.get("emailaddress")

    client_id = None
    if context.client:
        client_id = context.client.get("id")

    if user_id and client_id:
        matched_asset = await find_and_link_workstation(
            ticket_id=ticket_id,
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            client_id=client_id,
            halo_client=halo_client,
            ninja_client=ninja_client,
        )

    # === Strategies 2-4: Hostname from ticket text ===
    if not matched_asset:
        text = _collect_ticket_text(context.ticket, context.actions)

        # Strategy 2: Regex hostname extraction
        hostnames = _extract_hostnames(text) if text else []
        for hostname in hostnames:
            asset = await _try_hostname_match(hostname, halo_client, ninja_client)
            if asset:
                from .asset_matcher import _link_asset_to_ticket
                await _link_asset_to_ticket(
                    ticket_id, asset, halo_client, "ticket_text_hostname"
                )
                matched_asset = asset
                break

        # Strategy 3: Broad all-caps tokens → NinjaRMM
        if not matched_asset and ninja_client:
            already_tried = set(hostnames)
            caps_tokens = _extract_allcaps_tokens(text, exclude=already_tried)
            for token in caps_tokens:
                asset = await _try_ninja_hostname_search(
                    token, token, halo_client, ninja_client
                )
                if asset:
                    from .asset_matcher import _link_asset_to_ticket
                    await _link_asset_to_ticket(
                        ticket_id, asset, halo_client, "ninja_caps_token"
                    )
                    matched_asset = asset
                    break

        # Strategy 4: AI extraction
        if not matched_asset and anthropic_client:
            ai_hostname = await _ai_extract_hostname(
                text, anthropic_client, model
            )
            if ai_hostname:
                already_tried = set(hostnames)
                if ai_hostname not in already_tried:
                    asset = await _try_hostname_match(
                        ai_hostname, halo_client, ninja_client
                    )
                    if asset:
                        from .asset_matcher import _link_asset_to_ticket
                        await _link_asset_to_ticket(
                            ticket_id, asset, halo_client, "ai_extraction"
                        )
                        matched_asset = asset

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
    """
    Stage 2b: Evaluate contract notes and enrich if needed.

    Two-pass approach to avoid fetching PDFs unnecessarily:
    1. Quick evaluation: check existing notes for completeness (no PDF fetch)
    2. PDF fetch + regeneration: only for contracts that need it
    """
    contract_by_id: Dict[int, Dict[str, Any]] = {
        c["id"]: c for c in context.contracts if c.get("id")
    }

    contracts_to_check = [
        contract_by_id[cid] for cid in contract_ids if cid in contract_by_id
    ]

    logger.info(
        f"Contract enrichment: checking {len(contracts_to_check)} active contracts"
    )

    # ── Pass 1: Fetch recurring invoices (cheap) and evaluate notes ──
    contracts_needing_pdfs: List[Dict[str, Any]] = []
    # Cache invoice text so Pass 2 can reuse without re-fetching
    contract_invoice_cache: Dict[int, str] = {}

    for contract in contracts_to_check:
        cid = contract.get("id")
        if not cid:
            continue

        existing_note = str(contract.get("note") or contract.get("Notes") or "").strip()

        # Fetch recurring invoice (lightweight API call, no PDF)
        invoice_summary = ""
        try:
            invoices = await halo_client.get_recurring_invoices(contract_id=cid)
            if invoices:
                lines = []
                for inv in invoices:
                    for line in inv.get("lines", []):
                        desc = (
                            line.get("item_shortdescription")
                            or line.get("item_longdescription")
                            or "Unknown"
                        )
                        # Strip date range template tokens from description
                        desc = desc.split("$")[0].strip()
                        price = line.get("unit_price", "?")
                        qty = line.get("qty_order", "?")
                        net = line.get("net_amount", "?")
                        lines.append(f"  - {desc}: ${price} x {qty} = ${net}")
                if lines:
                    total = invoices[0].get("total", "?")
                    invoice_summary = (
                        f"Recurring Invoice (Total: ${total}):\n"
                        + "\n".join(lines)
                    )
                    contract_invoice_cache[cid] = invoice_summary
        except Exception as e:
            logger.warning(f"Failed to fetch recurring invoice for contract {cid}: {e}")

        # No notes at all — definitely needs enrichment
        if len(existing_note) < 50:
            logger.info(
                f"Contract {cid} (ref={contract.get('ref')}): needs notes "
                f"(current length={len(existing_note)})"
            )
            contracts_needing_pdfs.append(contract)
            continue

        # Has notes — evaluate completeness against the recurring invoice
        eval_content = (
            f"Do these contract notes look complete? Check for:\n"
            f"- Mentions of missing information, unavailable appendices, "
            f"or details that could not be found\n"
            f"- Missing covered services/products list\n"
            f"- Missing billing rates or SLA response times\n"
            f"- Generic placeholder content\n"
        )
        if invoice_summary:
            eval_content += (
                f"- Compare the services listed in the notes against the "
                f"recurring invoice below. If the notes list services that "
                f"are NOT on the recurring invoice, or miss services that "
                f"ARE on the invoice, the notes need improvement.\n\n"
                f"{invoice_summary}\n\n"
            )
        eval_content += (
            f"Respond with ONLY 'YES' if the notes are complete, "
            f"or 'NO' if they need improvement.\n\n"
            f"NOTES:\n{existing_note}"
        )

        eval_response = await client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": eval_content}],
        )

        verdict = eval_response.content[0].text.strip().upper()
        if "NO" in verdict:
            logger.info(
                f"Contract {cid} (ref={contract.get('ref')}): "
                f"notes need improvement"
            )
            contracts_needing_pdfs.append(contract)
        else:
            logger.info(
                f"Contract {cid} (ref={contract.get('ref')}): notes are adequate"
            )

    if not contracts_needing_pdfs:
        logger.info("All contract notes are adequate, skipping PDF fetch")
        return

    # ── Pass 2: Fetch PDFs and generate summaries ──
    # Recurring invoices were already fetched in Pass 1 (contract_invoice_cache)
    from context.fetcher import ContextFetcher
    contract_doc_texts: Dict[int, str] = {}

    for contract in contracts_needing_pdfs:
        cid = contract.get("id")
        if not cid:
            continue

        try:
            attachments = await halo_client.get_contract_attachments(cid)
            if not attachments:
                logger.debug(f"No attachments for contract {cid}")
                continue

            all_texts = []
            pdf_attachments = [
                att for att in attachments
                if att.get("filename", "").lower().endswith(".pdf")
            ]
            if not pdf_attachments:
                pdf_attachments = attachments[:1]

            for pdf_attach in pdf_attachments:
                try:
                    pdf_bytes = await halo_client.get_attachment_bytes(pdf_attach["id"])
                    if pdf_bytes:
                        text = ContextFetcher._extract_pdf_text(pdf_bytes)
                        if text:
                            filename = pdf_attach.get("filename", "unknown")
                            all_texts.append(f"--- {filename} ---\n{text}")
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch attachment {pdf_attach.get('id')} "
                        f"for contract {cid}: {e}"
                    )

            if all_texts:
                combined = "\n\n".join(all_texts)
                contract_doc_texts[cid] = combined
                logger.info(
                    f"Extracted {len(combined)} chars from {len(all_texts)} "
                    f"PDF(s) for contract {cid}"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch PDFs for contract {cid}: {e}")

    # Generate summaries
    for contract in contracts_needing_pdfs:
        cid = contract.get("id")
        if not cid:
            continue

        existing_note = str(contract.get("note") or contract.get("Notes") or "").strip()
        doc_text = contract_doc_texts.get(cid, "")
        invoice_text = contract_invoice_cache.get(cid, "")

        # No source data available — nothing to generate from
        if not doc_text and not invoice_text:
            logger.debug(f"Contract {cid}: no documents or invoices available, skipping")
            continue

        contract_text = _format_contract_for_summary(contract, doc_text)

        # Append recurring invoice data if available
        if invoice_text:
            contract_text += (
                f"\n\nRecurring Invoice (definitive source of billed services):\n"
                f"{invoice_text}"
            )

        if existing_note:
            user_content = (
                f"The existing notes for this contract are incomplete. Generate an "
                f"improved summary using the contract documents and recurring "
                f"invoice below. Incorporate any manually-entered information from "
                f"the existing notes that does not appear in the source documents.\n\n"
                f"EXISTING NOTES:\n{existing_note}\n\n"
                f"CONTRACT DATA:\n{contract_text}"
            )
        else:
            user_content = (
                f"Generate a concise summary for this contract:\n\n{contract_text}"
            )

        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=CONTRACT_SUMMARY_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        summary = response.content[0].text.strip()

        await halo_client.update_contract(contract_id=cid, note=summary)
        logger.info(
            f"Updated contract {cid} (ref={contract.get('ref')}) notes "
            f"({'regenerated' if existing_note else 'generated'})"
        )


async def _stage3_technical_triage(
    client: anthropic.AsyncAnthropic,
    model: str,
    halo_client: HaloClient,
    ninja_client: Optional[Any],
    mesh_client: Optional[Any],
    cipp_client: Optional[Any],
    ticket_id: int,
    context: ContextData,
    formatted_context: str,
    triage: Optional[TriageResult] = None,
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
    tools = _get_triage_tools(mesh_client=mesh_client, cipp_client=cipp_client)

    system = TECHNICAL_TRIAGE_SYSTEM_PROMPT + "\n\n" + formatted_context


    # Build user message with optional billing context
    user_content = (
        "Perform a thorough technical analysis of this ticket. "
        "Use tools to search for similar past tickets, relevant KB articles, "
        "and device data if applicable. Then provide your analysis as a "
        "structured note following the format in your instructions."
    )

    # Add billing note when prepaid time is exhausted and work isn't covered
    if triage and not triage.has_prepaid_time and not triage.work_covered_by_managed:
        user_content += (
            "\n\nBILLING NOTE: This client's prepaid time balance is exhausted "
            f"({triage.prepaid_balance}h remaining) and this work is not covered "
            "by their managed services agreement. Include a billing note in your "
            "analysis advising the technician that additional prepaid time may "
            "need to be purchased before or during this engagement."
        )

    messages: List[Dict[str, Any]] = [{
        "role": "user",
        "content": user_content,
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
                    tc.name, tc.input, halo_client, ninja_client, mesh_client,
                    cipp_client,
                )
                serialized = (
                    json.dumps(tool_result)
                    if isinstance(tool_result, (dict, list))
                    else str(tool_result)
                )
                if len(serialized) > 50_000:
                    logger.warning(
                        f"Tool result from {tc.name} truncated: "
                        f"{len(serialized)} chars → 50000"
                    )
                    serialized = (
                        serialized[:50_000]
                        + f"\n\n... [TRUNCATED — response was {len(serialized):,} chars, "
                        f"only first 50,000 shown]"
                    )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": serialized,
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


def _find_active_contracts(contracts: List[Dict[str, Any]]) -> List[int]:
    """
    Return IDs of all active contracts (started and not expired).

    Every active contract is a candidate for enrichment; Stage 2b will
    evaluate whether the existing notes are adequate.
    """
    ids = []
    for c in contracts:
        started = c.get("started", False)
        expired = c.get("expired", False)
        if not started or expired:
            continue

        cid = c.get("id")
        if not cid:
            continue

        ids.append(cid)

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
        lines.append(f"\nContract Documents:\n{doc_text}")
    return "\n".join(lines)


async def _execute_triage_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    halo_client: HaloClient,
    ninja_client: Optional[Any],
    mesh_client: Optional[Any] = None,
    cipp_client: Optional[Any] = None,
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
        elif tool_name == "get_recurring_invoices":
            return await halo_client.get_recurring_invoices(
                contract_id=tool_input.get("contract_id"),
                client_id=tool_input.get("client_id"),
            )
        elif tool_name == "set_ticket_priority":
            return await halo_client.update_ticket(
                ticket_id=tool_input["ticket_id"],
                priority_id=tool_input["priority_id"],
                sla_id=tool_input.get("sla_id"),
            )
        # Mesh Email Security read-only tools
        elif tool_name.startswith("mesh_") and mesh_client:
            if tool_name == "mesh_search_email_logs":
                return await mesh_client.search_email_logs(
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
            elif tool_name == "mesh_get_email_by_id":
                return await mesh_client.get_email_by_message_id(
                    message_id=tool_input["message_id"],
                    direction=tool_input.get("direction", "inbound"),
                )
            elif tool_name == "mesh_get_email_events":
                return await mesh_client.get_email_log_events(tool_input["queue_id"])
            elif tool_name == "mesh_search_customers":
                return await mesh_client.search_customers(
                    filter_term=tool_input["filter_term"],
                )
            return {"error": f"Unknown mesh tool: {tool_name}"}

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

        # CIPP read-only tools
        elif tool_name.startswith("cipp_") and cipp_client:
            method_map = {
                "cipp_list_tenants": lambda: cipp_client.list_tenants(),
                "cipp_list_users": lambda: cipp_client.list_users(tool_input["tenant_filter"]),
                "cipp_list_groups": lambda: cipp_client.list_groups(tool_input["tenant_filter"]),
                "cipp_list_user_groups": lambda: cipp_client.list_user_groups(
                    tool_input["tenant_filter"], tool_input["user_id"],
                ),
                "cipp_list_mailboxes": lambda: cipp_client.list_mailboxes(tool_input["tenant_filter"]),
                "cipp_list_mailbox_permissions": lambda: cipp_client.list_mailbox_permissions(
                    tool_input["tenant_filter"], tool_input["user_id"],
                ),
                "cipp_list_mailbox_rules": lambda: cipp_client.list_mailbox_rules(
                    tool_input["tenant_filter"], tool_input["user_id"],
                ),
                "cipp_list_devices": lambda: cipp_client.list_devices(tool_input["tenant_filter"]),
                "cipp_list_licenses": lambda: cipp_client.list_licenses(tool_input["tenant_filter"]),
                "cipp_list_sign_ins": lambda: cipp_client.list_sign_ins(
                    tenant_filter=tool_input["tenant_filter"],
                    user_id=tool_input.get("user_id"),
                    top=tool_input.get("top"),
                    days=tool_input.get("days"),
                ),
                "cipp_list_defender_state": lambda: cipp_client.list_defender_state(tool_input["tenant_filter"]),
                "cipp_list_conditional_access_policies": lambda: cipp_client.list_conditional_access_policies(
                    tool_input["tenant_filter"],
                ),
            }
            handler = method_map.get(tool_name)
            if handler:
                return await handler()
            return {"error": f"Unknown or write-only CIPP tool in triage: {tool_name}"}

        else:
            return {"error": f"Tool not available in triage: {tool_name}"}
    except Exception as e:
        logger.warning(f"Triage tool {tool_name} failed: {e}")
        return {"error": str(e)}


def _get_triage_tools(
    mesh_client: Optional[Any] = None,
    cipp_client: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Get the read-only tool definitions for technical triage.

    This is a subset of the full tool list — only tools that read data.
    Write operations (create/update/close ticket, create note) are excluded.
    """
    from halo.tools import get_halo_tools
    from ninja.tools import get_ninja_tools

    # Whitelist of Halo tool names available in triage
    # (read-only tools + set_ticket_priority for priority assessment)
    triage_halo_tools = {
        "get_ticket", "get_user", "get_client", "get_asset",
        "search_tickets", "search_kb", "get_kb_article",
        "get_client_contracts", "get_recurring_invoices",
        "set_ticket_priority",
    }

    tools = [t for t in get_halo_tools() if t["name"] in triage_halo_tools]

    # Add all NinjaRMM tools (all read-only)
    try:
        tools.extend(get_ninja_tools())
    except ImportError:
        pass

    # Add Mesh Email Security tools (all read-only)
    if mesh_client:
        try:
            from mesh.tools import get_mesh_tools
            tools.extend(get_mesh_tools())
        except ImportError:
            pass

    # Add CIPP read-only tools
    if cipp_client:
        try:
            from cipp.tools import get_cipp_read_tools
            tools.extend(get_cipp_read_tools())
        except ImportError:
            pass

    return tools
