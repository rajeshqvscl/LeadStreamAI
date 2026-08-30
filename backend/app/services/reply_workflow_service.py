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
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DECLINE-PHRASE DETECTION
# ---------------------------------------------------------------------------
# Deterministic hard-stop list: if ANY of these phrases appears in a reply,
# the lead is treated as NOT_INTERESTED and follow-ups stop immediately.
# This is independent of (and overrides) the LLM intent classification.
# Each entry is (regex_pattern, readable_label). Patterns match against
# lowercased, whitespace-collapsed reply text.
DECLINE_PATTERNS = [
    (r"\bwe\s+will\s+pass\s+on\s+this\s+opportunity\b", "We will pass on this opportunity"),
    (r"\bpass\s+on\s+this\s+opportunity\b", "Pass on this opportunity"),
    (r"\bwe\s+only\s+invest\s+in\b", "We only invest in"),
    (r"\bwe\s+only\s+do\b", "We only do"),
    # Negative lookahead excludes only positive forwarding idioms like
    # "We will pass this along to our team" (meaning they'll forward it),
    # while still catching genuine declines like "We will pass this opportunity".
    (r"\bwe\s+will\s+pass\b(?!\s+(?:this|it|that|along)\s+(?:along|on|to|over)\b)", "We will pass"),
    (r"\bwe(?:'|’)\s*ll\s+pass\b(?!\s+(?:this|it|that|along)\s+(?:along|on|to|over)\b)", "We'll pass"),
    (r"\bnot\s+a\s+current\s+fit\b", "Not a current fit"),
    (r"\bnot\s+fit\s+for\s+us\b", "Not fit for us"),
    (r"\bno\s*,?\s*thank\s*(?:you|s)?\b", "No thank you"),
    (r"\bplease\s+share\s+a\s+detailed\s+deck\b", "Please share a detailed deck"),
    (r"\bpass\s+from\s+us\b", "Pass from us"),
    (r"\bpass\s+for\s+now\b", "Pass for now"),
    (r"\bnot\s+within\s+our\s+mandate\b", "Not within our mandate"),
    (r"\btoo\s+early\s+for\s+us\b", "Too early for us"),
]


def detect_decline_phrase(text: str | None) -> str | None:
    """
    Returns the readable label of the first decline phrase found in the reply text,
    or None if the text contains no known decline phrase.

    Matching is case-insensitive and robust to extra whitespace / punctuation
    (e.g. 'No, thankyou', 'We will pass.', 'not a current fit for us').
    """
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).lower()
    for pattern, label in DECLINE_PATTERNS:
        if re.search(pattern, normalized):
            return label
    return None


def determine_followup_status(intent: str) -> str:
    """
    Maps an LLM classification intent to the correct followup_status.

    Intent → Status mapping:
        NOT_INTERESTED    → STOPPED            (end sequence)
        INTERESTED        → MEETING_REQUIRED   (stop auto-emails, trigger meeting workflow)
        MEETING_REQUESTED → MEETING_REQUIRED   (same as INTERESTED)
        NEEDS_MORE_INFO   → STOPPED            (end sequence — any reply stops follow-ups)
        Any other/None    → STOPPED            (SAFETY: ANY human reply stops automation;
                                                lead can be manually re-activated after review)
    """
    if intent == 'NOT_INTERESTED':
        new_status = 'STOPPED'
    elif intent in ('INTERESTED', 'MEETING_REQUESTED'):
        new_status = 'MEETING_REQUIRED'
    elif intent == 'NEEDS_MORE_INFO':
        new_status = 'STOPPED'
    else:
        logger.warning(
            "Unknown reply_intent '%s' — defaulting to STOPPED. "
            "Any human reply must pause automated followups.",
            intent
        )
        new_status = 'STOPPED'

    logger.info("Reply classification: intent=%s -> followup_status=%s", intent, new_status)
    return new_status
