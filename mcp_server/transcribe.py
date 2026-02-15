"""Call recording transcription via Whisper + Claude analysis."""

import io
import logging
import re
from typing import Any, Dict, Optional

import anthropic
import httpx
import openai
from mutagen.mp3 import MP3

from config import get_settings
from halo.client import HaloClient
from .prompts import CALL_TRANSCRIPTION_PROMPT, SPEAKER_CONTEXT_TEMPLATE

logger = logging.getLogger(__name__)

# Whisper API limit is 25 MB
MAX_WHISPER_SIZE = 25 * 1024 * 1024

ANALYSIS_MODEL = "claude-sonnet-4-20250514"


CHARGERATE_REMOTE_SUPPORT = 1
CHARGERATE_NO_CHARGE = 0


def _parse_charge_classification(analysis: str) -> int:
    """Parse the Charge Classification section to determine the charge rate ID.

    Returns CHARGERATE_NO_CHARGE (0) if 'No Charge' is found,
    otherwise CHARGERATE_REMOTE_SUPPORT (1) as the default.
    """
    # Look for the Charge Classification section
    match = re.search(
        r"##\s*Charge Classification\s*\n(.*?)(?=\n##|\Z)",
        analysis,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        section = match.group(1).strip().lower()
        if "no charge" in section:
            return CHARGERATE_NO_CHARGE
    return CHARGERATE_REMOTE_SUPPORT


def _format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _get_mp3_duration_seconds(mp3_bytes: bytes) -> float | None:
    """Extract duration from MP3 bytes. Returns seconds or None."""
    try:
        audio = MP3(io.BytesIO(mp3_bytes))
        return audio.info.length
    except Exception:
        logger.debug("Could not read MP3 duration", exc_info=True)
        return None


def _format_call_metadata(call_metadata: Dict[str, Any]) -> str:
    """Format 1Stream call metadata as a markdown section for the note."""
    lines = ["## Call Details"]

    direction = call_metadata.get("direction")
    if direction:
        lines.append(f"- **Direction**: {direction}")

    caller_number = call_metadata.get("caller_number")
    caller_name = call_metadata.get("caller_name")
    if caller_number or caller_name:
        parts = [p for p in [caller_number, caller_name] if p]
        lines.append(f"- **From**: {' — '.join(parts)}")

    dialled_number = call_metadata.get("dialled_number")
    extension = call_metadata.get("extension")
    if dialled_number or extension:
        parts = [p for p in [dialled_number, f"Ext {extension}" if extension else None] if p]
        lines.append(f"- **To**: {' — '.join(parts)}")

    dt = call_metadata.get("datetime")
    if dt:
        lines.append(f"- **Date/Time**: {dt}")

    duration = call_metadata.get("duration")
    if duration:
        lines.append(f"- **Duration**: {duration}")

    return "\n".join(lines)


async def _download_from_url(url: str) -> tuple[bytes, str | None]:
    """Download audio bytes from a URL. Returns (bytes, filename)."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()

    # Try to extract filename from URL path
    from urllib.parse import urlparse
    path = urlparse(url).path
    filename = path.rsplit("/", 1)[-1] if "/" in path else None

    return resp.content, filename


async def _download_from_halo(
    halo_client: HaloClient, ticket_id: int, attachment_id: int,
) -> tuple[bytes, str | None]:
    """Download audio bytes from a Halo attachment. Returns (bytes, filename)."""
    mp3_bytes = await halo_client.get_attachment_bytes(attachment_id)

    # Look up the filename from attachment metadata
    filename = None
    try:
        attachments = await halo_client.get_ticket_attachments(ticket_id)
        for att in attachments:
            if att.get("id") == attachment_id:
                filename = att.get("filename")
                break
    except Exception:
        logger.debug("Could not fetch attachment metadata for filename", exc_info=True)

    return mp3_bytes, filename


async def _get_speaker_context(
    halo_client: HaloClient,
    ticket_id: int,
) -> str:
    """
    Fetch ticket data to build speaker identification context.

    Returns a formatted string to append to the prompt, or empty string
    if no useful context is available.
    """
    try:
        ticket = await halo_client.get_ticket(ticket_id)
    except Exception:
        logger.debug("Could not fetch ticket for speaker context", exc_info=True)
        return ""

    participants = []

    # Customer name from ticket
    user_name = ticket.get("user_name")
    if user_name:
        participants.append(f"- **Customer**: {user_name}")

    # Agent name from ticket
    agent_id = ticket.get("agent_id")
    if agent_id:
        agent_name = await halo_client.get_agent_name(agent_id)
        if agent_name:
            participants.append(f"- **Agent (Technician)**: {agent_name}")

    if not participants:
        return ""

    return SPEAKER_CONTEXT_TEMPLATE.format(
        participants="\n".join(participants) + "\n",
    )


async def transcribe_call_recording(
    halo_client: HaloClient,
    ticket_id: Optional[int] = None,
    attachment_id: Optional[int] = None,
    url: Optional[str] = None,
    post_note: bool = True,
    # Override params for webhook automation
    audio_bytes: Optional[bytes] = None,
    speaker_context_override: Optional[str] = None,
    duration_override: Optional[float] = None,
    note_datetime: Optional[str] = None,
    call_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Download an MP3 call recording and transcribe it with Whisper + Claude.

    Provide either `url` (any HTTP URL to an audio file), `attachment_id`
    (a Halo ticket attachment), or `audio_bytes` (pre-downloaded MP3).

    Args:
        halo_client: Authenticated Halo API client
        ticket_id: Ticket to post the note to (required if post_note=True)
        attachment_id: Halo attachment ID to download
        url: Direct URL to an audio file
        post_note: If True, post the transcription as a private note on the ticket
        audio_bytes: Pre-downloaded MP3 bytes (skips download step)
        speaker_context_override: Speaker context string (skips Halo ticket lookup)
        duration_override: Call duration in seconds (skips MP3 duration parsing)
        note_datetime: ISO 8601 datetime to set as "Date Done" on the note
        call_metadata: Dict of 1Stream call fields to include in the note

    Returns:
        The structured transcription/summary text
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is not configured. "
            "It is required for Whisper speech-to-text transcription."
        )

    if not audio_bytes and not url and not attachment_id:
        raise ValueError("Provide either audio_bytes, url, or attachment_id")

    if post_note and not ticket_id:
        raise ValueError("ticket_id is required when post_note is true")

    # 1. Get the audio bytes
    filename = None
    if audio_bytes:
        mp3_bytes = audio_bytes
        logger.info(f"Using pre-downloaded audio: {len(mp3_bytes)} bytes")
    elif url:
        logger.info(f"Downloading audio from URL: {url}")
        mp3_bytes, filename = await _download_from_url(url)
    else:
        logger.info(f"Downloading attachment {attachment_id} for ticket {ticket_id}")
        mp3_bytes, filename = await _download_from_halo(
            halo_client, ticket_id, attachment_id,
        )

    if not mp3_bytes:
        raise ValueError("Downloaded file is empty (0 bytes)")

    file_size = len(mp3_bytes)
    if file_size > MAX_WHISPER_SIZE:
        raise ValueError(
            f"File is too large for Whisper: "
            f"{file_size / 1024 / 1024:.1f} MB (max {MAX_WHISPER_SIZE / 1024 / 1024:.0f} MB)"
        )

    # Resolve duration
    if duration_override is not None:
        duration_seconds = duration_override
    else:
        duration_seconds = _get_mp3_duration_seconds(mp3_bytes)
    duration_str = _format_duration(duration_seconds) if duration_seconds else None

    logger.info(
        f"Audio ready: {file_size} bytes ({file_size / 1024:.1f} KB)"
        f"{f' ({duration_str})' if duration_str else ''}"
        f"{f' [{filename}]' if filename else ''}"
    )

    # 2. Transcribe with OpenAI Whisper
    logger.info("Sending to Whisper for speech-to-text transcription")
    whisper_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    audio_file = io.BytesIO(mp3_bytes)
    audio_file.name = filename or "recording.mp3"

    try:
        whisper_response = await whisper_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )
    except openai.BadRequestError as e:
        logger.error(f"Whisper 400 error: {e.message} (body={e.body})")
        raise ValueError(f"Whisper rejected the audio: {e.message}") from e

    raw_transcript = whisper_response.strip() if isinstance(whisper_response, str) else str(whisper_response).strip()
    if not raw_transcript:
        raise ValueError("Whisper returned an empty transcription")

    logger.info(f"Whisper transcription complete: {len(raw_transcript)} characters")

    # 3. Build the analysis prompt with speaker context
    prompt = CALL_TRANSCRIPTION_PROMPT

    if speaker_context_override:
        prompt += speaker_context_override
        logger.info("Added speaker context override to prompt")
    elif ticket_id:
        speaker_context = await _get_speaker_context(halo_client, ticket_id)
        if speaker_context:
            prompt += speaker_context
            logger.info("Added speaker identification context from ticket")

    user_message = prompt + "\n\n"
    if duration_str:
        user_message += f"Call duration: {duration_str}\n\n"
    user_message += f"---\n\n# Raw Transcript\n\n{raw_transcript}"

    # 4. Send transcript to Claude for structured analysis
    logger.info("Sending transcript to Claude for analysis")
    claude_client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=httpx.Timeout(120.0, connect=10.0),
    )

    response = await claude_client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=8000,
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
    )

    analysis = response.content[0].text if response.content else ""
    if not analysis:
        raise ValueError("Claude returned an empty analysis")

    usage = response.usage
    logger.info(
        f"Analysis complete: {usage.input_tokens} input tokens, "
        f"{usage.output_tokens} output tokens"
    )

    # 5. Parse charge classification from analysis
    chargerate = _parse_charge_classification(analysis)
    charge_label = "No Charge" if chargerate == CHARGERATE_NO_CHARGE else "Remote Support"
    logger.info(f"Charge classification: {charge_label} (chargerate={chargerate})")

    # 6. Post as private note on the ticket
    if post_note and ticket_id:
        meta_parts = []
        if filename:
            meta_parts.append(f"File: {filename}")
        if duration_str:
            meta_parts.append(f"Duration: {duration_str}")
        meta_parts.append(f"Whisper: whisper-1")
        meta_parts.append(f"Analysis: {ANALYSIS_MODEL}")
        meta_parts.append(f"Tokens: {usage.input_tokens} in / {usage.output_tokens} out")

        # Build the note with optional call metadata
        note_sections = [
            f"## AI Call Transcription (Claude)\n\n{analysis}",
        ]
        if call_metadata:
            # Add duration to metadata for display
            if duration_str and "duration" not in call_metadata:
                call_metadata["duration"] = duration_str
            note_sections.append(_format_call_metadata(call_metadata))

        note_sections.append(f"---\n*{' | '.join(meta_parts)}*")
        note_text = "\n\n".join(note_sections)

        # Convert duration to hours for time tracking
        timetaken = round(duration_seconds / 3600, 2) if duration_seconds else None

        try:
            await halo_client.create_ticket_note(
                ticket_id=ticket_id,
                note=note_text,
                hiddenfromuser=True,
                timetaken=timetaken,
                datetime_override=note_datetime,
                chargerate=chargerate,
            )
            logger.info(
                f"Posted transcription note on ticket {ticket_id}"
                f" (charge={charge_label}, timetaken={timetaken}h)"
                f"{f' (datetime={note_datetime})' if note_datetime else ''}"
            )
        except Exception:
            logger.exception(
                f"Failed to post transcription note on ticket {ticket_id} "
                f"(transcription still returned to caller)"
            )

    return analysis
