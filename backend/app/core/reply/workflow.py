"""
Reply Workflow
Single source: intent -> state transitions.
Maps classification results to pipeline state updates.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.pipeline.state_machine import LeadState
from app.core.reply.classifier import ClassificationResult


@dataclass
class LeadUpdate:
    """Complete lead update derived from reply classification"""
    is_responded: bool = True
    replied_at: datetime | None = None
    email_status: str = "REPLIED"
    reply_intent: str | None = None
    followup_status: str = "STOPPED"  # safe default: any reply pauses automation
    pipeline_state: LeadState = LeadState.REPLIED
    sentiment_score: int = 0
    urgency_level: str = "MEDIUM"
    deal_size: str | None = None
    rejection_reason: str | None = None


class ReplyWorkflow:
    """
    Centralized reply-to-state mapping.
    This is the SINGLE SOURCE OF TRUTH for reply handling.
    """

    # Intent -> Followup Status
    INTENT_TO_FOLLOWUP_STATUS = {
        "NOT_INTERESTED": "STOPPED",
        "INTERESTED": "MEETING_REQUIRED",
        "MEETING_REQUESTED": "MEETING_REQUIRED",
        "MEETING_SCHEDULED": "MEETING_REQUIRED",
        "NEEDS_MORE_INFO": "STOPPED",
    }

    # Intent -> Email Status
    INTENT_TO_EMAIL_STATUS = {
        "NOT_INTERESTED": "CLOSED",
        "INTERESTED": "REPLIED",
        "MEETING_REQUESTED": "REPLIED",
        "MEETING_SCHEDULED": "REPLIED",
        "NEEDS_MORE_INFO": "REPLIED",
    }

    # Intent -> Pipeline State
    INTENT_TO_PIPELINE_STATE = {
        "NOT_INTERESTED": LeadState.CLOSED_LOST,
        "INTERESTED": LeadState.MEETING_REQUIRED,
        "MEETING_REQUESTED": LeadState.MEETING_REQUIRED,
        "MEETING_SCHEDULED": LeadState.MEETING_REQUIRED,
        "NEEDS_MORE_INFO": LeadState.REPLIED,
    }

    def apply(self, classification: ClassificationResult) -> LeadUpdate:
        """
        Map classification result to complete lead update.
        """
        intent = classification.intent

        # SAFETY RULE: ANY reply that doesn't map to a known classification
        # (unknown, None, or LLM fallback failure) STOPS the followup sequence
        # immediately. A human reply means automation must pause — the lead can
        # be manually re-activated after review.
        followup_status = self.INTENT_TO_FOLLOWUP_STATUS.get(intent, "STOPPED")
        email_status = self.INTENT_TO_EMAIL_STATUS.get(intent, "REPLIED")
        pipeline_state = self.INTENT_TO_PIPELINE_STATE.get(intent, LeadState.REPLIED)

        IST = timezone(timedelta(hours=5, minutes=30))

        return LeadUpdate(
            is_responded=True,
            replied_at=datetime.now(IST),
            email_status=email_status,
            reply_intent=intent,
            followup_status=followup_status,
            pipeline_state=pipeline_state,
            sentiment_score=classification.sentiment_score,
            urgency_level=classification.urgency_level,
            deal_size=classification.deal_size,
            rejection_reason=classification.rejection_reason,
        )

    def get_followup_status(self, intent: str | None) -> str:
        """Get followup_status for intent (legacy compatibility). Unknown -> STOPPED."""
        return self.INTENT_TO_FOLLOWUP_STATUS.get(intent, "STOPPED")

    def get_email_status(self, intent: str | None) -> str:
        """Get email_status for intent (legacy compatibility)"""
        return self.INTENT_TO_EMAIL_STATUS.get(intent, "REPLIED")


# Singleton
_workflow: ReplyWorkflow | None = None


def get_reply_workflow() -> ReplyWorkflow:
    global _workflow
    if _workflow is None:
        _workflow = ReplyWorkflow()
    return _workflow


def determine_followup_status(intent: str | None) -> str:
    """Legacy function for backward compatibility"""
    return get_reply_workflow().get_followup_status(intent)
