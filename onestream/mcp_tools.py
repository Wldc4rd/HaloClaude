"""
MCP Tool registrations for 1Stream (BVOIP) call recording.

Registers 1Stream tools on the existing HaloClaude MCP server
so they are available to Claude Desktop and other MCP clients.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp_server.server import mcp, get_halo_client
from .client import OneStreamClient

logger = logging.getLogger(__name__)

# OneStreamClient instance, set during app startup
_onestream_client: Optional[OneStreamClient] = None


def set_onestream_client(client: OneStreamClient) -> None:
    """Set the 1Stream client instance for tools to use."""
    global _onestream_client
    _onestream_client = client


def get_onestream_client() -> OneStreamClient:
    """Get the 1Stream client, raising if not initialized."""
    if _onestream_client is None:
        raise RuntimeError("OneStreamClient not initialized. Is ONESTREAM_ENABLED=true?")
    return _onestream_client


# =============================================================================
# 1Stream Call Recording Tools
# =============================================================================

@mcp.tool(
    description="Search 1Stream call logs by date range. Returns call metadata "
    "including caller, duration, direction, ticket link, and recording URL. "
    "Use this to find calls for a specific time period or extension."
)
async def onestream_search_calls(
    start_date: str,
    end_date: str,
    ext: str = "",
    page_size: int = 25,
) -> List[Dict[str, Any]]:
    """
    Search 1Stream call logs.

    Args:
        start_date: Start date (any format, e.g. 2026-02-13, 2/13/2026, 2026-02-13 10:00)
        end_date: End date (same format)
        ext: Extension number filter (empty for all extensions)
        page_size: Number of results (default 25)
    """
    logger.info(f"MCP: onestream_search_calls: {start_date} to {end_date}")
    client = get_onestream_client()
    return await client.get_call_logs(
        start_date=start_date,
        end_date=end_date,
        ext=ext,
        page_size=page_size,
    )


@mcp.tool(
    description="Download and transcribe a 1Stream call recording. Provide the "
    "DownloadRecording URL from onestream_search_calls. Downloads the MP3 via "
    "1Stream API, transcribes with Whisper, then analyzes with Claude. "
    "If ticket_id is provided, posts the result as a private note on the ticket. "
    "IMPORTANT: Always pass call_end_time (ActualEndTime or EndDate from the "
    "call log) so the note gets the correct 'Date Done' timestamp. Also pass "
    "call metadata fields (direction, caller_name, caller_number, "
    "dialled_number, extension, talk_time_seconds) for richer notes."
)
async def onestream_get_call_recording(
    download_url: str,
    ticket_id: Optional[int] = None,
    post_note: bool = True,
    call_end_time: Optional[str] = None,
    direction: Optional[str] = None,
    caller_name: Optional[str] = None,
    caller_number: Optional[str] = None,
    dialled_number: Optional[str] = None,
    extension: Optional[str] = None,
    talk_time_seconds: Optional[int] = None,
) -> str:
    """
    Download and transcribe a 1Stream call recording.

    Args:
        download_url: The DownloadRecording URL from a call log entry
        ticket_id: Halo ticket ID to post the transcription note to
        post_note: If true and ticket_id is set, post as private note (default true)
        call_end_time: Call end time from the call log (ActualEndTime or EndDate).
                         Sets the note's "Date Done" to when the call ended.
        direction: Call direction ("Inbound" or "Outbound")
        caller_name: Caller/originator name from OriginatedByName
        caller_number: Caller ID number from CallerIDNumber
        dialled_number: Dialled number from DialledNumber
        extension: Extension name from ExtensionName
        talk_time_seconds: Talk time in seconds from TalkTimeSeconds
    """
    logger.info(
        f"MCP: onestream_get_call_recording: ticket_id={ticket_id}, "
        f"url={download_url[:60]}..."
    )
    from mcp_server.transcribe import transcribe_call_recording

    onestream = get_onestream_client()
    halo = get_halo_client()

    # Download via 1Stream client (authenticated)
    audio_bytes = await onestream.download_recording(download_url)

    # Build call metadata dict if any fields provided
    call_metadata = None
    if any([direction, caller_name, caller_number, dialled_number, extension, call_end_time]):
        call_metadata = {}
        if direction:
            call_metadata["direction"] = direction
        if caller_number:
            call_metadata["caller_number"] = caller_number
        if caller_name:
            call_metadata["caller_name"] = caller_name
        if dialled_number:
            call_metadata["dialled_number"] = dialled_number
        if extension:
            call_metadata["extension"] = extension
        if call_end_time:
            call_metadata["datetime"] = call_end_time

    # Build speaker context from 1Stream metadata
    speaker_context = None
    if direction and (caller_name or extension):
        from mcp_server.prompts import SPEAKER_CONTEXT_TEMPLATE
        participants = []
        if direction.lower() == "inbound":
            if caller_name:
                participants.append(f"- **Customer**: {caller_name}")
            if extension:
                participants.append(f"- **Agent (Technician)**: {extension}")
        else:
            if extension:
                participants.append(f"- **Customer**: {extension}")
            if caller_name:
                participants.append(f"- **Agent (Technician)**: {caller_name}")
        if participants:
            if direction.lower() == "inbound":
                dir_text = (
                    f"This was an **inbound** call — the customer ({caller_name or 'unknown'}) "
                    f"called in to the IT support line."
                )
            else:
                dir_text = (
                    f"This was an **outbound** call — the technician ({extension or 'unknown'}) "
                    f"called the customer ({caller_name or 'unknown'})."
                )
            speaker_context = SPEAKER_CONTEXT_TEMPLATE.format(
                participants="\n".join(participants) + "\n",
                direction=dir_text,
            )

    return await transcribe_call_recording(
        halo_client=halo,
        ticket_id=ticket_id,
        post_note=post_note,
        audio_bytes=audio_bytes,
        note_datetime=call_end_time,
        call_metadata=call_metadata,
        speaker_context_override=speaker_context,
        duration_override=float(talk_time_seconds) if talk_time_seconds else None,
    )
