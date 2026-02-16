"""
Ticket Pipeline

Unified multi-stage pipeline for ticket processing with two modes:

  mode="triage" (new tickets):
    0.  User/Client Resolution
    0.5 Junk Filter — auto-close spam/OOO/bounce
    1.  Triage Classification
    2b. Contract Enrichment
    2c. Asset Auto-Assignment
    2a. Sales Path (if no contract)
    3.  Technical Triage

  mode="review" (existing tickets, triggered by Halo runbook):
    0.  User/Client Resolution
    0.5 Junk Filter
    2c. Asset Auto-Assignment
    R.  Conversation Review — AI reads conversation, sets status or closes
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
    REVIEW_SYSTEM_PROMPT,
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
    route: str = ""  # "technical"
    reasoning: str = ""


async def run_ticket_pipeline(
    ticket_id: int,
    halo_client: HaloClient,
    ninja_client: Optional[Any],
    anthropic_api_key: str,
    model: str,
    mode: str = "triage",
    review_model: Optional[str] = None,
    sop_kb_search_term: Optional[str] = "SOP",
    sop_kb_filter_tag: Optional[str] = "ai-context",
    max_sop_articles: int = 10,
    max_sop_article_length: int = 2000,
    max_contract_doc_length: int = 5000,
    mesh_client: Optional[Any] = None,
    cipp_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run the ticket pipeline in the specified mode.

    Modes:
        "triage" — full triage for new tickets (default)
        "review" — AI conversation review for existing tickets

    Returns a summary dict of what happened (for logging).
    """
    result: Dict[str, Any] = {
        "ticket_id": ticket_id,
        "mode": mode,
        "stages_completed": [],
        "errors": [],
    }

    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
    is_review = mode == "review"

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

    logger.info(f"Ticket pipeline starting for ticket {ticket_id} (mode={mode})")

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
    # STAGE 0.5: Junk Filter (both modes)
    # ========================================
    try:
        junk_closed = await _stage05_junk_filter(
            halo_client, client, model, ticket_id, context,
        )
        if junk_closed:
            result["stages_completed"].append("junk_filter")
            result["route"] = "auto_closed"
            result["junk_reason"] = junk_closed
            logger.info(f"Ticket {ticket_id} auto-closed as junk: {junk_closed}")
            return result
    except Exception as e:
        logger.warning(f"Junk filter failed for ticket {ticket_id}: {e}")
        result["errors"].append(f"Junk filter failed: {e}")
        # Non-fatal, continue pipeline

    triage = None
    is_leif_it = False

    # ========================================
    # TRIAGE-ONLY: Classification, Contract Enrichment
    # ========================================
    if not is_review:
        # Check for Leif IT clients — bypass triage/contract/sales checks
        if context.client:
            is_leif_it = context.client.get("top_level_id") == JUSTIN_TOP_LEVEL_ID

        if is_leif_it:
            logger.info(
                f"Leif IT client detected for ticket {ticket_id}, "
                f"routing directly to Justin (agent {JUSTIN_AGENT_ID})"
            )
            result["stages_completed"].append("leif_it_routing")
            result["route"] = "technical"
        else:
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

    # ========================================
    # STAGE 2c: Asset Auto-Assignment (both modes)
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
                formatted_context = formatter.format(context)
        except Exception as e:
            logger.warning(f"Asset auto-assignment failed for ticket {ticket_id}: {e}")
            result["errors"].append(f"Asset auto-assignment failed: {e}")

    if not is_review:
        # ========================================
        # STAGE 3: Technical Triage
        # ========================================
        if is_leif_it or (triage and triage.route == "technical"):
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
    else:
        # ========================================
        # STAGE R: Conversation Review (review mode only)
        # ========================================
        try:
            await _stageR_conversation_review(
                client, review_model or model, halo_client,
                ticket_id, context, formatted_context,
            )
            result["stages_completed"].append("conversation_review")
        except Exception as e:
            logger.exception(f"Conversation review failed for ticket {ticket_id}: {e}")
            result["errors"].append(f"Conversation review failed: {e}")

    logger.info(f"Ticket pipeline complete for ticket {ticket_id}: {result}")
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


async def _stage05_junk_filter(
    halo_client: HaloClient,
    anthropic_client: anthropic.AsyncAnthropic,
    model: str,
    ticket_id: int,
    context: ContextData,
) -> Optional[str]:
    """
    Stage 0.5: Detect and auto-close junk tickets.

    Returns the junk reason string if the ticket was closed, None otherwise.
    """
    from .junk_detector import (
        should_skip_junk_detection,
        classify_ticket_as_junk,
        ai_confirm_junk,
    )

    summary = context.ticket.get("summary", "")
    details = context.ticket.get("details", "")

    # Extract sender email from first action or user
    sender_email = ""
    if context.actions:
        first_action = context.actions[0]
        sender_email = first_action.get("emailfrom", "") or ""
    if not sender_email and context.user:
        sender_email = context.user.get("emailaddress", "") or ""

    # Extract first action body
    first_action_body = ""
    if context.actions:
        first_action_body = context.actions[0].get("note", "") or ""

    # Get agent_id and action_count for safety checks
    agent_id = context.ticket.get("agent_id")
    if isinstance(agent_id, dict):
        agent_id = agent_id.get("id")
    action_count = len(context.actions) if context.actions else 0
    combined_text = f"{summary} {details} {first_action_body}"

    # Safety pre-check
    if should_skip_junk_detection(sender_email, agent_id, action_count, combined_text):
        logger.debug(f"Ticket {ticket_id}: skipping junk detection (safety pre-check)")
        return None

    # Deterministic classification
    junk = classify_ticket_as_junk(summary, details, sender_email, first_action_body)
    if not junk:
        return None

    # High confidence: close immediately
    # Medium confidence: confirm with AI first
    if junk.confidence == "medium":
        content = f"{summary}\n\n{details}\n\n{first_action_body}"
        confirmed = await ai_confirm_junk(
            anthropic_client, model, summary, sender_email, content,
        )
        if not confirmed:
            logger.info(
                f"Ticket {ticket_id}: AI rejected junk classification "
                f"(pattern={junk.pattern}, reason={junk.reason})"
            )
            return None

    # Close the ticket
    closure_note = (
        f"<b>Auto-Closed: {junk.pattern.replace('_', ' ').title()}</b><br><br>"
        f"<b>Reason:</b> {junk.reason}<br>"
        f"<b>Confidence:</b> {junk.confidence}<br><br>"
        f"<i>This ticket was automatically closed by the triage pipeline. "
        f"If this was closed in error, please reopen the ticket.</i>"
    )

    await halo_client.close_ticket(ticket_id=ticket_id, note=closure_note)

    logger.info(
        f"Ticket {ticket_id} auto-closed as junk: "
        f"pattern={junk.pattern}, confidence={junk.confidence}, "
        f"reason={junk.reason}"
    )

    return junk.reason


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

    triage.route = "technical"

    logger.info(
        f"Triage result: type={triage.client_type}, "
        f"active_contract={triage.has_active_contract}, "
        f"prepaid={triage.has_prepaid_time} ({triage.prepaid_balance}h), "
        f"route={triage.route}, "
        f"reasoning={triage.reasoning}"
    )

    return triage


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
        _collect_ticket_summary_text,
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
        text = _collect_ticket_summary_text(context.ticket)

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


async def _stageR_conversation_review(
    client: anthropic.AsyncAnthropic,
    model: str,
    halo_client: HaloClient,
    ticket_id: int,
    context: ContextData,
    formatted_context: str,
) -> None:
    """
    Stage R: AI conversation review for existing tickets.

    Reads the full conversation, determines the correct status, and
    either updates the status or closes the ticket.
    """
    from datetime import datetime, timedelta, timezone

    # Step 1: Check review recency — skip if reviewed within 24 hours
    previous_reviews = []
    if context.actions:
        for action in context.actions:
            note = action.get("note", "") or ""
            if "[AUTO-REVIEW" in note:
                # Parse action date
                action_date_str = action.get("actiondate") or action.get("dateoccurred")
                if action_date_str:
                    try:
                        action_date = datetime.fromisoformat(
                            action_date_str.replace("Z", "+00:00")
                        )
                        if action_date > datetime.now(timezone.utc) - timedelta(hours=24):
                            logger.info(
                                f"Ticket {ticket_id}: skipping review — "
                                f"reviewed within last 24 hours"
                            )
                            return
                    except (ValueError, TypeError):
                        pass
                previous_reviews.append(note)

    # Step 2: Build conversation history for AI
    conversation_lines = []
    if context.actions:
        for action in context.actions:
            who = action.get("who", "Unknown")
            note = action.get("note", "") or ""
            outcome = action.get("outcome", "") or ""
            action_date = action.get("actiondate") or action.get("dateoccurred") or ""
            action_type = action.get("actiontypename", "") or ""

            if not note and not outcome:
                continue

            entry = f"[{action_date}] {who}"
            if action_type:
                entry += f" ({action_type})"
            entry += ":"
            if note:
                entry += f"\n{note}"
            if outcome:
                entry += f"\nOutcome: {outcome}"
            conversation_lines.append(entry)

    conversation_text = "\n\n---\n\n".join(conversation_lines)

    # Include previous review notes as context
    review_history = ""
    if previous_reviews:
        review_history = (
            "\n\nPREVIOUS AUTOMATED REVIEWS:\n"
            + "\n---\n".join(previous_reviews)
        )

    # Ticket metadata
    current_status_id = context.ticket.get("status_id")
    if isinstance(current_status_id, dict):
        current_status_id = current_status_id.get("id")
    current_status_name = ""
    status_obj = context.ticket.get("status")
    if isinstance(status_obj, dict):
        current_status_name = status_obj.get("name", "")
    elif isinstance(context.ticket.get("status_id"), dict):
        current_status_name = context.ticket["status_id"].get("name", "")

    agent_name = ""
    agent_id = context.ticket.get("agent_id")
    if isinstance(agent_id, dict):
        agent_name = agent_id.get("name", "")
        agent_id = agent_id.get("id")

    user_content = (
        f"Review this ticket and determine the correct action.\n\n"
        f"TICKET SUMMARY: {context.ticket.get('summary', '')}\n"
        f"CURRENT STATUS: {current_status_name} (ID: {current_status_id})\n"
        f"ASSIGNED AGENT: {agent_name or 'Unassigned'}\n"
        f"PRIORITY: {context.ticket.get('priority_name', 'Unknown')}\n\n"
        f"CONVERSATION HISTORY:\n{conversation_text}"
        f"{review_history}"
    )

    system = REVIEW_SYSTEM_PROMPT + "\n\n" + formatted_context

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    text = response.content[0].text.strip()
    # Handle markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(text)

    assessment = data.get("assessment", "active")
    confidence = data.get("confidence", "low")
    reasoning = data.get("reasoning", "")

    logger.info(
        f"Ticket {ticket_id} review result: "
        f"assessment={assessment}, confidence={confidence}, "
        f"reasoning={reasoning}"
    )

    # Step 3: Take action based on assessment
    if assessment == "junk" and confidence == "high":
        note = (
            f"<b>[AUTO-REVIEW: CLOSED - JUNK]</b><br><br>"
            f"<b>Assessment:</b> This ticket appears to be junk/spam.<br>"
            f"<b>Reasoning:</b> {reasoning}<br><br>"
            f"<i>If this was closed in error, please reopen the ticket.</i>"
        )
        await halo_client.close_ticket(ticket_id=ticket_id, note=note)

    elif assessment == "resolved" and confidence == "high":
        note = (
            f"<b>[AUTO-REVIEW: CLOSED - RESOLVED]</b><br><br>"
            f"<b>Assessment:</b> This ticket appears to be resolved.<br>"
            f"<b>Reasoning:</b> {reasoning}<br><br>"
            f"<i>If this was closed in error, please reopen the ticket.</i>"
        )
        await halo_client.close_ticket(ticket_id=ticket_id, note=note)

        # Notify assigned technician
        if agent_id:
            logger.info(
                f"Ticket {ticket_id}: notifying agent {agent_name} "
                f"(id={agent_id}) of auto-closure"
            )

    elif assessment == "resolved" and confidence == "medium":
        note = (
            f"<b>[AUTO-REVIEW: APPEARS RESOLVED]</b><br><br>"
            f"<b>Assessment:</b> This ticket appears to be resolved but "
            f"confidence is not high enough for auto-closure.<br>"
            f"<b>Reasoning:</b> {reasoning}<br><br>"
            f"<i>Please review and close if appropriate.</i>"
        )
        await halo_client.create_ticket_note(
            ticket_id=ticket_id, note=note, hiddenfromuser=True,
        )

    elif assessment == "waiting_customer":
        if current_status_id != 22:
            await halo_client.update_ticket(ticket_id=ticket_id, status_id=22)
            note = (
                f"<b>[AUTO-REVIEW: STATUS → WAITING FOR CUSTOMER]</b><br><br>"
                f"<b>Reasoning:</b> {reasoning}"
            )
            await halo_client.create_ticket_note(
                ticket_id=ticket_id, note=note, hiddenfromuser=True,
            )
        else:
            logger.debug(
                f"Ticket {ticket_id}: already in Waiting for Customer status"
            )

    elif assessment == "waiting_us":
        if current_status_id != 23:
            await halo_client.update_ticket(ticket_id=ticket_id, status_id=23)
            note = (
                f"<b>[AUTO-REVIEW: NEEDS ATTENTION]</b><br><br>"
                f"<b>Assessment:</b> Customer is waiting for our response.<br>"
                f"<b>Reasoning:</b> {reasoning}"
            )
            await halo_client.create_ticket_note(
                ticket_id=ticket_id, note=note, hiddenfromuser=True,
            )
        else:
            logger.debug(
                f"Ticket {ticket_id}: already in User Update status"
            )

    else:
        # "active" or low confidence — no action
        logger.info(
            f"Ticket {ticket_id}: review assessment is '{assessment}' "
            f"(confidence={confidence}), no action taken"
        )

    # Step 4: Auto-assign unassigned tickets that weren't closed
    ticket_was_closed = (
        (assessment == "junk" and confidence == "high")
        or (assessment == "resolved" and confidence == "high")
    )
    REAL_AGENT_IDS = {CHARLIE_AGENT_ID, JUSTIN_AGENT_ID}
    if not ticket_was_closed and agent_id not in REAL_AGENT_IDS:
        # Determine correct agent using same logic as triage
        top_level_id = None
        if context.client:
            top_level_id = context.client.get("top_level_id")

        if top_level_id == JUSTIN_TOP_LEVEL_ID:
            assign_agent_id = JUSTIN_AGENT_ID
            assign_agent_name = "Justin"
        else:
            assign_agent_id = CHARLIE_AGENT_ID
            assign_agent_name = "Charlie"

        await halo_client.update_ticket(
            ticket_id=ticket_id, agent_id=assign_agent_id,
        )
        note = (
            f"<b>[AUTO-REVIEW: ASSIGNED → {assign_agent_name}]</b><br><br>"
            f"<b>Reasoning:</b> Ticket was unassigned during review. "
            f"Auto-assigned based on client routing."
        )
        await halo_client.create_ticket_note(
            ticket_id=ticket_id, note=note, hiddenfromuser=True,
        )
        logger.info(
            f"Ticket {ticket_id}: auto-assigned to {assign_agent_name} "
            f"(agent_id={assign_agent_id})"
        )


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
