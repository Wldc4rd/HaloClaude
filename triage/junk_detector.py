"""
Junk Ticket Detector

Deterministic pattern matching + optional AI confirmation to identify
tickets that should be auto-closed: spam, auto-replies, bounce-backs,
and pure automated notifications.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class JunkDetectionResult:
    """Result of junk ticket classification."""

    is_junk: bool
    confidence: str  # "high" or "medium"
    reason: str  # human-readable explanation
    pattern: str  # "auto_reply", "bounce", "spam", "automated_notification"


# ── Monitoring tool domains that should NEVER be flagged as junk ──
MONITORING_ALLOWLIST = {
    "ninjarmm.com",
    "ninjarmm.zendesk.com",
    "sentinelone.net",
    "sentinelone.com",
    "zorus.com",
    "zorustech.com",
    "archon.com",
    "todyl.com",
    "datto.com",
    "kaseya.com",
    "dattobackup.com",
    "microsoft.com",
    "microsoftonline.com",
    "emailsecurity.app",
    "huntress.io",
    "huntresslabs.com",
    "autoelevate.com",
    "servosity.com",
    "printix.net",
    "keeper.io",
    "keepersecurity.com",
    "powerdmarc.com",
    "scalepadsoftware.com",
    "screenconnect.com",
    "connectwise.com",
}

# ── Auto-reply / Out-of-Office patterns ──
AUTO_REPLY_SUBJECT_PREFIXES = (
    "automatic reply:",
    "auto:",
    "autoreply:",
    "out of office:",
    "ooo:",
    "absence:",
    "away:",
    "auto-reply:",
)

AUTO_REPLY_BODY_PHRASES = [
    "i am currently out of the office",
    "i'm currently out of the office",
    "i will be out of the office",
    "i'm out of the office",
    "i am away from",
    "i'm away from",
    "limited access to email",
    "i will respond when i return",
    "i will have limited access",
    "i am on vacation",
    "i'm on vacation",
    "i am on leave",
    "i am on holiday",
]

# ── Bounce / NDR patterns ──
BOUNCE_SUBJECT_PREFIXES = (
    "undeliverable:",
    "delivery status notification",
    "mail delivery failed",
    "returned mail:",
    "failure notice",
    "undelivered mail",
    "mail delivery subsystem",
)

BOUNCE_SENDER_PREFIXES = (
    "mailer-daemon@",
    "postmaster@",
    "bounced-",
)

BOUNCE_BODY_PHRASES = [
    "550 ",
    "5.1.1",
    "5.2.1",
    "5.1.0",
    "recipient rejected",
    "user unknown",
    "mailbox unavailable",
    "mailbox not found",
    "address rejected",
    "could not be delivered",
    "delivery has failed",
    "not delivered",
    "message was undeliverable",
]

# ── Spam / Marketing patterns ──
MARKETING_SENDER_DOMAINS = {
    "mailchimp.com",
    "sendgrid.net",
    "constantcontact.com",
    "hubspot.com",
    "campaign-archive.com",
    "mailgun.net",
    "aweber.com",
    "getresponse.com",
    "activecampaign.com",
    "drip.com",
    "convertkit.com",
    "mailerlite.com",
    "sendinblue.com",
    "brevo.com",
    "emma.com",
    "moosend.com",
    "benchmark.email",
}

MARKETING_BODY_PHRASES = [
    "click here to unsubscribe",
    "manage your preferences",
    "email preferences",
    "you are receiving this email because",
    "you opted in",
    "marketing communication",
    "to stop receiving these emails",
    "to unsubscribe from this mailing list",
    "update your email preferences",
    "opt out of",
]

# ── Automated notification patterns ──
NOTIFICATION_SENDER_PREFIXES = (
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
    "notifications@",
    "alert@",
    "alerts@",
)

NOTIFICATION_BODY_PHRASES = [
    "this is an automated message",
    "do not reply to this email",
    "this message was automatically generated",
    "this is a system-generated",
    "this email was sent automatically",
    "please do not reply to this message",
    "this is a notification only",
    "no action is required",
]

# ── Security keywords that should prevent auto-closure ──
SECURITY_KEYWORDS = [
    "breach",
    "compromised",
    "malware",
    "ransomware",
    "virus detected",
    "threat detected",
    "suspicious activity",
    "unauthorized access",
    "security incident",
    "data breach",
]


def _get_sender_domain(email: str) -> str:
    """Extract domain from email address."""
    if "@" in email:
        return email.split("@", 1)[1].lower().strip()
    return ""


def _is_monitoring_sender(email: str) -> bool:
    """Check if the sender is from a known monitoring tool."""
    domain = _get_sender_domain(email)
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in MONITORING_ALLOWLIST)


def _has_security_content(text: str) -> bool:
    """Check if the text mentions active security incidents."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in SECURITY_KEYWORDS)


def should_skip_junk_detection(
    sender_email: str,
    agent_id: Optional[int],
    action_count: int,
    combined_text: str,
) -> bool:
    """
    Pre-check: should we skip junk detection entirely?

    Returns True if junk detection should be skipped (ticket is likely legitimate).
    """
    # Already assigned to an agent — someone chose to work on it
    if agent_id:
        return True

    # Real conversation happening (3+ actions)
    if action_count >= 3:
        return True

    # Sender is a monitoring tool
    if sender_email and _is_monitoring_sender(sender_email):
        return True

    # Content mentions active security incidents
    if combined_text and _has_security_content(combined_text):
        return True

    return False


def classify_ticket_as_junk(
    summary: str,
    details: str,
    sender_email: str,
    first_action_body: str,
) -> Optional[JunkDetectionResult]:
    """
    Classify a ticket as junk based on deterministic pattern matching.

    Returns a JunkDetectionResult if junk is detected, None otherwise.
    High confidence results can be acted on immediately.
    Medium confidence results should be confirmed by AI.
    """
    summary_lower = summary.lower().strip()
    sender_lower = sender_email.lower().strip()
    combined_body = (details + " " + first_action_body).lower()

    # === Pattern 1: Auto-Reply / Out-of-Office ===
    result = _check_auto_reply(summary_lower, combined_body)
    if result:
        return result

    # === Pattern 2: Bounce / NDR ===
    result = _check_bounce(summary_lower, sender_lower, combined_body)
    if result:
        return result

    # === Pattern 3: Spam / Marketing ===
    result = _check_spam(summary_lower, sender_lower, combined_body)
    if result:
        return result

    # === Pattern 4: Automated Notification ===
    result = _check_notification(summary_lower, sender_lower, combined_body)
    if result:
        return result

    return None


def _check_auto_reply(
    summary_lower: str, body_lower: str
) -> Optional[JunkDetectionResult]:
    """Check for auto-reply / out-of-office patterns."""
    # Subject starts with known auto-reply prefix
    if any(summary_lower.startswith(prefix) for prefix in AUTO_REPLY_SUBJECT_PREFIXES):
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason=f"Subject line indicates auto-reply: '{summary_lower[:80]}'",
            pattern="auto_reply",
        )

    # Subject contains "out of office" as a phrase
    if re.search(r"\bout of (?:the )?office\b", summary_lower):
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason="Subject contains 'out of office'",
            pattern="auto_reply",
        )

    # Body contains strong OOO indicators
    ooo_matches = sum(1 for phrase in AUTO_REPLY_BODY_PHRASES if phrase in body_lower)
    if ooo_matches >= 2:
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason="Body contains multiple out-of-office phrases",
            pattern="auto_reply",
        )

    # Single body match — medium confidence (needs AI confirmation)
    if ooo_matches == 1:
        return JunkDetectionResult(
            is_junk=True,
            confidence="medium",
            reason="Body contains out-of-office phrase (single match)",
            pattern="auto_reply",
        )

    return None


def _check_bounce(
    summary_lower: str, sender_lower: str, body_lower: str
) -> Optional[JunkDetectionResult]:
    """Check for bounce-back / non-delivery report patterns."""
    # Subject starts with bounce prefix
    if any(summary_lower.startswith(prefix) for prefix in BOUNCE_SUBJECT_PREFIXES):
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason=f"Subject indicates bounce/NDR: '{summary_lower[:80]}'",
            pattern="bounce",
        )

    # Sender is a mailer-daemon or postmaster
    if any(sender_lower.startswith(prefix) for prefix in BOUNCE_SENDER_PREFIXES):
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason=f"Sender is a mail system address: {sender_lower}",
            pattern="bounce",
        )

    # Body contains SMTP error codes
    smtp_matches = sum(1 for phrase in BOUNCE_BODY_PHRASES if phrase in body_lower)
    if smtp_matches >= 2:
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason="Body contains multiple bounce/NDR indicators",
            pattern="bounce",
        )

    return None


def _check_spam(
    summary_lower: str, sender_lower: str, body_lower: str
) -> Optional[JunkDetectionResult]:
    """Check for spam / marketing email patterns."""
    sender_domain = _get_sender_domain(sender_lower)

    # Sender is from a known marketing platform
    is_marketing_sender = sender_domain in MARKETING_SENDER_DOMAINS

    # Body has marketing unsubscribe language
    marketing_matches = sum(
        1 for phrase in MARKETING_BODY_PHRASES if phrase in body_lower
    )

    # Marketing sender + any marketing body phrase = high confidence
    if is_marketing_sender and marketing_matches >= 1:
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason=f"Marketing platform sender ({sender_domain}) with unsubscribe content",
            pattern="spam",
        )

    # Marketing sender alone = medium confidence
    if is_marketing_sender:
        return JunkDetectionResult(
            is_junk=True,
            confidence="medium",
            reason=f"Sender is from marketing platform: {sender_domain}",
            pattern="spam",
        )

    # Multiple marketing phrases without marketing sender = medium
    if marketing_matches >= 2:
        return JunkDetectionResult(
            is_junk=True,
            confidence="medium",
            reason="Body contains multiple marketing/unsubscribe phrases",
            pattern="spam",
        )

    # IMPORTANT: "unsubscribe" alone is NOT enough — many legitimate emails have it
    return None


def _check_notification(
    summary_lower: str, sender_lower: str, body_lower: str
) -> Optional[JunkDetectionResult]:
    """Check for pure automated notifications that require no action."""
    # Must be from a no-reply sender
    is_noreply = any(
        sender_lower.startswith(prefix) for prefix in NOTIFICATION_SENDER_PREFIXES
    )
    if not is_noreply:
        return None

    # Body must contain notification-only language
    notification_matches = sum(
        1 for phrase in NOTIFICATION_BODY_PHRASES if phrase in body_lower
    )

    if notification_matches >= 2:
        return JunkDetectionResult(
            is_junk=True,
            confidence="high",
            reason="No-reply sender with automated notification language",
            pattern="automated_notification",
        )

    if notification_matches == 1:
        return JunkDetectionResult(
            is_junk=True,
            confidence="medium",
            reason="No-reply sender with possible notification content",
            pattern="automated_notification",
        )

    return None


# ── AI Confirmation ──

JUNK_CONFIRMATION_PROMPT = """\
You are reviewing an IT support ticket to determine if it is junk that should \
be automatically closed. Junk tickets include:
- Auto-reply / Out-of-Office responses
- Bounce-back / Non-Delivery Reports
- Spam / marketing emails that created tickets
- Automated system notifications that require no human action

IMPORTANT SAFETY RULES:
- If there is ANY indication this is a real support request, respond NO
- If a human is asking for help or reporting a problem, respond NO
- If it's a monitoring alert (NinjaRMM, SentinelOne, Zorus, Huntress, etc.), respond NO
- If you're unsure, respond NO

Respond with ONLY "YES" if this is clearly junk, or "NO" if it might be legitimate.

TICKET SUMMARY: {summary}
SENDER: {sender}
TICKET CONTENT:
{content}
"""


async def ai_confirm_junk(
    anthropic_client,
    model: str,
    summary: str,
    sender_email: str,
    content: str,
) -> bool:
    """
    Use AI to confirm a borderline junk detection.

    Returns True if the AI confirms this is junk.
    """
    prompt = JUNK_CONFIRMATION_PROMPT.format(
        summary=summary,
        sender=sender_email,
        content=content[:3000],  # Limit content to avoid excessive tokens
    )

    try:
        response = await anthropic_client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.content[0].text.strip().upper()
        confirmed = "YES" in answer
        logger.info(
            f"AI junk confirmation: {'YES' if confirmed else 'NO'} "
            f"(raw: {answer!r})"
        )
        return confirmed
    except Exception as e:
        logger.warning(f"AI junk confirmation failed: {e}")
        # On failure, don't confirm — let the ticket through
        return False
