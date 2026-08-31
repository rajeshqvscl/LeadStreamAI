"""
Unit tests for Reply Workflow (apply, get_followup_status, get_email_status).
Pure logic — no DB, no network.
"""

import pytest

from app.core.reply.workflow import (
    ReplyWorkflow,
    LeadUpdate,
    determine_followup_status,
)
from app.core.reply.classifier import ClassificationResult
from app.core.pipeline.state_machine import LeadState


def _make_classification(intent="NOT_INTERESTED", **overrides) -> ClassificationResult:
    defaults = {
        "intent": intent,
        "source": "LLM",
        "sentiment_score": 50,
        "urgency_level": "MEDIUM",
        "deal_size": None,
        "rejection_reason": None,
        "confidence": 0.9,
        "raw_llm_output": None,
    }
    defaults.update(overrides)
    return ClassificationResult(**defaults)


class TestApplyIntents:
    """Test apply() for each known intent."""

    def test_not_interested(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="NOT_INTERESTED"))
        assert result.is_responded is True
        assert result.followup_status == "STOPPED"
        assert result.email_status == "CLOSED"
        assert result.pipeline_state == LeadState.CLOSED_LOST
        assert result.replied_at is not None

    def test_interested(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="INTERESTED"))
        assert result.is_responded is True
        assert result.followup_status == "MEETING_REQUIRED"
        assert result.email_status == "REPLIED"
        assert result.pipeline_state == LeadState.MEETING_REQUIRED

    def test_meeting_requested(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="MEETING_REQUESTED"))
        assert result.is_responded is True
        assert result.followup_status == "MEETING_REQUIRED"
        assert result.email_status == "REPLIED"
        assert result.pipeline_state == LeadState.MEETING_REQUIRED

    def test_meeting_scheduled(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="MEETING_SCHEDULED"))
        assert result.is_responded is True
        assert result.followup_status == "MEETING_REQUIRED"
        assert result.email_status == "REPLIED"
        assert result.pipeline_state == LeadState.MEETING_REQUIRED

    def test_needs_more_info(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="NEEDS_MORE_INFO"))
        assert result.is_responded is True
        assert result.followup_status == "STOPPED"
        assert result.email_status == "REPLIED"
        assert result.pipeline_state == LeadState.REPLIED


class TestApplyUnknownIntent:
    """Unknown/None intents should fall back to safe defaults."""

    def test_none_intent(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent=None))
        assert result.is_responded is True
        assert result.followup_status == "STOPPED"
        assert result.email_status == "REPLIED"
        assert result.pipeline_state == LeadState.REPLIED

    def test_unknown_string_intent(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="SOME_UNKNOWN_INTENT"))
        assert result.followup_status == "STOPPED"
        assert result.email_status == "REPLIED"
        assert result.pipeline_state == LeadState.REPLIED


class TestApplyClassificationFields:
    """Verify classification fields propagate to LeadUpdate."""

    def test_sentiment_score_propagated(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="INTERESTED", sentiment_score=85))
        assert result.sentiment_score == 85

    def test_urgency_level_propagated(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="INTERESTED", urgency_level="HIGH"))
        assert result.urgency_level == "HIGH"

    def test_deal_size_propagated(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(intent="INTERESTED", deal_size="$1M"))
        assert result.deal_size == "$1M"

    def test_rejection_reason_propagated(self):
        wf = ReplyWorkflow()
        result = wf.apply(_make_classification(
            intent="NOT_INTERESTED", rejection_reason="Not a fit"
        ))
        assert result.rejection_reason == "Not a fit"


class TestGetFollowupStatus:
    """get_followup_status maps intents to followup status strings."""

    def test_known_intents(self):
        wf = ReplyWorkflow()
        assert wf.get_followup_status("NOT_INTERESTED") == "STOPPED"
        assert wf.get_followup_status("INTERESTED") == "MEETING_REQUIRED"
        assert wf.get_followup_status("MEETING_REQUESTED") == "MEETING_REQUIRED"
        assert wf.get_followup_status("MEETING_SCHEDULED") == "MEETING_REQUIRED"
        assert wf.get_followup_status("NEEDS_MORE_INFO") == "STOPPED"

    def test_unknown_intent_returns_stopped(self):
        wf = ReplyWorkflow()
        assert wf.get_followup_status("UNKNOWN") == "STOPPED"

    def test_none_intent_returns_stopped(self):
        wf = ReplyWorkflow()
        assert wf.get_followup_status(None) == "STOPPED"


class TestGetEmailStatus:
    """get_email_status maps intents to email status strings."""

    def test_known_intents(self):
        wf = ReplyWorkflow()
        assert wf.get_email_status("NOT_INTERESTED") == "CLOSED"
        assert wf.get_email_status("INTERESTED") == "REPLIED"
        assert wf.get_email_status("MEETING_REQUESTED") == "REPLIED"
        assert wf.get_email_status("MEETING_SCHEDULED") == "REPLIED"
        assert wf.get_email_status("NEEDS_MORE_INFO") == "REPLIED"

    def test_unknown_intent_returns_replied(self):
        wf = ReplyWorkflow()
        assert wf.get_email_status("UNKNOWN") == "REPLIED"

    def test_none_intent_returns_replied(self):
        wf = ReplyWorkflow()
        assert wf.get_email_status(None) == "REPLIED"


class TestDetermineFollowupStatusLegacy:
    """Legacy function should delegate to workflow correctly."""

    def test_legacy_function_works(self):
        assert determine_followup_status("NOT_INTERESTED") == "STOPPED"
        assert determine_followup_status("INTERESTED") == "MEETING_REQUIRED"
        assert determine_followup_status(None) == "STOPPED"
