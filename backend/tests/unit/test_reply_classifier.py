"""
Unit tests for ReplyClassifier (classify + _parse_llm_result)
Uses minimal mocking — no real LLM calls.
"""

from unittest.mock import MagicMock

import pytest

from app.core.reply.classifier import ClassificationResult, ReplyClassifier


class TestClassifyDeclinePhrase:
    """Tests for deterministic decline phrase detection."""

    def test_decline_phrase_not_interested(self):
        classifier = ReplyClassifier(llm_client=None)
        result = classifier.classify("Not interested, thanks.")
        assert result.intent == "NOT_INTERESTED"
        assert result.source == "DECLINE_PHRASE"
        assert result.confidence == 1.0

    def test_decline_phrase_we_will_pass(self):
        classifier = ReplyClassifier(llm_client=None)
        result = classifier.classify("We will pass on this opportunity.")
        assert result.intent == "NOT_INTERESTED"
        assert result.source == "DECLINE_PHRASE"
        assert result.rejection_reason is not None

    def test_decline_phrase_no_thank_you(self):
        classifier = ReplyClassifier(llm_client=None)
        result = classifier.classify("No thank you.")
        assert result.intent == "NOT_INTERESTED"
        assert result.source == "DECLINE_PHRASE"


class TestClassifyFallback:
    """Tests for fallback when no decline phrase and no LLM."""

    def test_no_decline_no_llm_returns_fallback(self):
        classifier = ReplyClassifier(llm_client=None)
        result = classifier.classify("I'd love to schedule a meeting next week.")
        assert result.source == "FALLBACK"
        assert result.intent is None
        assert result.confidence == 0.0

    def test_classifier_without_llm_client_always_fallback(self):
        classifier = ReplyClassifier(llm_client=None)
        result = classifier.classify("Let me review the deck and get back.")
        assert result.source == "FALLBACK"


class TestClassifyLLM:
    """Tests for LLM path when client is available."""

    def test_calls_classify_with_llm(self):
        mock_client = MagicMock()
        classifier = ReplyClassifier(llm_client=mock_client)
        # Manually stub _classify_with_llm to avoid real LLM call
        expected = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score=80,
            confidence=0.9,
        )
        classifier._classify_with_llm = MagicMock(return_value=expected)
        result = classifier.classify("I'm interested in this opportunity.")
        assert result.intent == "INTERESTED"
        assert result.source == "LLM"
        classifier._classify_with_llm.assert_called_once_with("I'm interested in this opportunity.")


class TestParseLlmResult:
    """Tests for _parse_llm_result validation and defaults."""

    def test_valid_intent(self):
        classifier = ReplyClassifier(llm_client=None)
        llm_output = {
            "intent": "MEETING_REQUESTED",
            "sentiment_score": 75,
            "urgency_level": "HIGH",
        }
        result = classifier._parse_llm_result(llm_output, "some body")
        assert result.intent == "MEETING_REQUESTED"
        assert result.sentiment_score == 75
        assert result.urgency_level == "HIGH"
        assert result.source == "LLM"
        assert result.confidence == 0.9

    def test_invalid_intent_set_to_none(self):
        classifier = ReplyClassifier(llm_client=None)
        llm_output = {
            "intent": "INVALID_INTENT",
            "sentiment_score": 50,
            "urgency_level": "MEDIUM",
        }
        result = classifier._parse_llm_result(llm_output, "body")
        assert result.intent is None

    def test_sentiment_score_clamped_above_100(self):
        classifier = ReplyClassifier(llm_client=None)
        llm_output = {
            "intent": "INTERESTED",
            "sentiment_score": 150,
            "urgency_level": "MEDIUM",
        }
        result = classifier._parse_llm_result(llm_output, "body")
        assert result.sentiment_score == 100

    def test_sentiment_score_clamped_below_0(self):
        classifier = ReplyClassifier(llm_client=None)
        llm_output = {
            "intent": "INTERESTED",
            "sentiment_score": -10,
            "urgency_level": "MEDIUM",
        }
        result = classifier._parse_llm_result(llm_output, "body")
        assert result.sentiment_score == 0

    def test_missing_fields_use_defaults(self):
        classifier = ReplyClassifier(llm_client=None)
        llm_output = {
            "intent": "INTERESTED",
        }
        result = classifier._parse_llm_result(llm_output, "body")
        assert result.sentiment_score == 50  # default when missing
        assert result.urgency_level == "MEDIUM"
        assert result.deal_size is None
        assert result.rejection_reason is None

    def test_non_int_sentiment_defaults_to_50(self):
        classifier = ReplyClassifier(llm_client=None)
        llm_output = {
            "intent": "INTERESTED",
            "sentiment_score": "not_a_number",
            "urgency_level": "MEDIUM",
        }
        result = classifier._parse_llm_result(llm_output, "body")
        assert result.sentiment_score == 50


# Run with: pytest tests/unit/test_reply_classifier.py -v
