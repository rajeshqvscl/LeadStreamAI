"""
Reply Classification Validator
Validates AI output against business rules BEFORE database writes.

Flow:
    LLM → Raw JSON → Schema Validation → Business Rules → State Machine → DB

This ensures AI can RECOMMEND state, not OWN the state machine.
"""

import logging
from dataclasses import dataclass

from app.core.pipeline.state_machine import LeadState, get_pipeline
from app.core.reply.classifier import ClassificationResult

logger = logging.getLogger(__name__)

# Valid intents that the AI can produce
VALID_INTENTS = {
    "MEETING_REQUESTED",
    "INTERESTED",
    "NEEDS_MORE_INFO",
    "NOT_INTERESTED",
}

# Valid urgency levels
VALID_URGENCY = {"HIGH", "MEDIUM", "LOW"}

# Sentiment score bounds
MIN_SENTIMENT = 0
MAX_SENTIMENT = 100


@dataclass
class ValidationResult:
    """Result of validating an AI classification output."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    sanitized: ClassificationResult | None = None


def validate_classification(
    result: ClassificationResult,
    lead_state: str | None = None,
    current_followup_status: str | None = None,
) -> ValidationResult:
    """
    Validate an AI classification result against schema + business rules.

    Args:
        result: Raw classification from ReplyClassifier
        lead_state: Current pipeline state of the lead
        current_followup_status: Current followup_status of the lead

    Returns:
        ValidationResult with is_valid, errors, warnings, and sanitized result
    """
    errors = []
    warnings = []
    sanitized = ClassificationResult(
        intent=result.intent,
        source=result.source,
        sentiment_score=result.sentiment_score,
        urgency_level=result.urgency_level,
        deal_size=result.deal_size,
        rejection_reason=result.rejection_reason,
        confidence=result.confidence,
        raw_llm_output=result.raw_llm_output,
    )

    # --- Schema Validation ---

    # 1. Intent must be valid or None (None = fallback/unknown)
    if result.intent is not None and result.intent not in VALID_INTENTS:
        errors.append(f"Invalid intent '{result.intent}' — must be one of {VALID_INTENTS}")
        sanitized.intent = None  # Safe fallback

    # 2. Sentiment score must be in range
    if not isinstance(result.sentiment_score, (int, float)):
        warnings.append(f"Sentiment score not numeric: {result.sentiment_score}")
        sanitized.sentiment_score = 50  # Default neutral
    elif result.sentiment_score < MIN_SENTIMENT or result.sentiment_score > MAX_SENTIMENT:
        warnings.append(f"Sentiment score out of range: {result.sentiment_score}")
        sanitized.sentiment_score = max(MIN_SENTIMENT, min(MAX_SENTIMENT, result.sentiment_score))

    # 3. Urgency level must be valid
    if result.urgency_level not in VALID_URGENCY:
        warnings.append(f"Invalid urgency '{result.urgency_level}' — defaulting to MEDIUM")
        sanitized.urgency_level = "MEDIUM"

    # 4. Confidence must be between 0 and 1
    if not (0 <= result.confidence <= 1):
        warnings.append(f"Confidence out of range: {result.confidence}")
        sanitized.confidence = max(0.0, min(1.0, result.confidence))

    # --- Business Rule Validation ---
    # Use sanitized sentiment for all business rule checks (after clamping above)
    sentiment = sanitized.sentiment_score

    # 5. Intent-sentiment consistency
    if result.intent == "NOT_INTERESTED" and sentiment > 30:
        warnings.append(
            f"NOT_INTERESTED but sentiment={result.sentiment_score} — "
            f"lowering sentiment to 15 for consistency"
        )
        sanitized.sentiment_score = 15

    if result.intent in ("MEETING_REQUESTED", "INTERESTED") and sentiment < 40:
        warnings.append(
            f"Positive intent ({result.intent}) but low sentiment={sentiment} — "
            f"raising sentiment to 60"
        )
        sanitized.sentiment_score = 60

    # 6. Confidence threshold for automation
    if result.confidence < 0.5 and result.source == "LLM":
        warnings.append(
            f"Low LLM confidence ({result.confidence}) — "
            f"intent '{result.intent}' may need manual review"
        )

    # 7. State machine guard: check if this transition is valid
    if lead_state and result.intent:
        try:
            from app.core.reply.workflow import get_reply_workflow
            workflow = get_reply_workflow()
            target_state = workflow.INTENT_TO_PIPELINE_STATE.get(result.intent)

            if target_state:
                pipeline = get_pipeline()
                # Create a minimal lead object for transition check
                from app.core.pipeline.state_machine import Lead as PipelineLead
                test_lead = PipelineLead(
                    id=0,
                    pipeline_state=lead_state,
                    followup_status=current_followup_status or "",
                )
                if not pipeline.can_transition(
                    LeadState(lead_state), target_state, test_lead
                ):
                    warnings.append(
                        f"State transition {lead_state} → {target_state.value} "
                        f"may not be valid — proceeding but flagging"
                    )
        except Exception as e:
            warnings.append(f"State machine check failed: {e}")

    # 8. Source integrity
    if result.source not in ("DECLINE_PHRASE", "LLM", "FALLBACK"):
        warnings.append(f"Unknown source '{result.source}' — keeping as-is")

    is_valid = len(errors) == 0

    if errors:
        logger.error(f"Classification validation FAILED: {errors}")
    if warnings:
        logger.warning(f"Classification validation warnings: {warnings}")

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        sanitized=sanitized if is_valid else None,
    )
