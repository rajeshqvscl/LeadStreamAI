"""
Centralized reply workflow handler.
Applies business rules based on LLM classification result.
This is the single source of truth for reply-to-state transitions.

Responsibilities:
  - Map LLM intent to followup_status
  - Keep is_responded as an analytics-only flag (not a decision point)
  - Isolate business logic from Gmail sync code
"""

import logging

logger = logging.getLogger(__name__)


def determine_followup_status(intent: str) -> str:
    """
    Maps an LLM classification intent to the correct followup_status.

    Intent → Status mapping:
        NOT_INTERESTED    → STOPPED            (end sequence)
        INTERESTED        → MEETING_REQUIRED   (stop auto-emails, trigger meeting workflow)
        MEETING_REQUESTED → MEETING_REQUIRED   (same as INTERESTED)
        NEEDS_MORE_INFO   → ACTIVE             (continue follow-up sequence)
        Any other/None    → ACTIVE             (AI failure — don't silently stop outreach)

    IMPORTANT: Unknown/unexpected intents default to ACTIVE, NOT STOPPED.
    An LLM timeout, JSON parse failure, or prompt regression should never
    silently end a lead's sequence. Defaulting to ACTIVE keeps the sequence
    alive for manual review rather than killing it permanently.
    """
    if intent == 'NOT_INTERESTED':
        new_status = 'STOPPED'
    elif intent in ('INTERESTED', 'MEETING_REQUESTED'):
        new_status = 'MEETING_REQUIRED'
    elif intent == 'NEEDS_MORE_INFO':
        new_status = 'ACTIVE'
    else:
        logger.warning(
            "Unknown reply_intent '%s' — defaulting to ACTIVE to avoid "
            "silently stopping outreach. Fix the LLM prompt or handle this intent.",
            intent
        )
        new_status = 'ACTIVE'

    logger.info("Reply classification: intent=%s -> followup_status=%s", intent, new_status)
    return new_status
