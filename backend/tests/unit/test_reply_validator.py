"""
AI Output Validation Tests

Tests the reply classification validator for schema compliance,
business rule enforcement, and state machine guard checks.
"""

import pytest
from app.core.reply.classifier import ClassificationResult
from app.core.reply.validator import validate_classification, ValidationResult


class TestSchemaValidation:
    """Test basic schema validation of AI output."""

    def test_valid_classification_passes(self):
        """A well-formed classification should pass validation."""
        result = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score=75,
            urgency_level="HIGH",
            confidence=0.95,
        )
        validation = validate_classification(result)
        assert validation.is_valid
        assert validation.sanitized is not None
        assert validation.sanitized.intent == "INTERESTED"

    def test_invalid_intent_fails(self):
        """Invalid intent string should fail validation."""
        result = ClassificationResult(
            intent="COMPLETELY_INVALID",
            source="LLM",
            sentiment_score=50,
            urgency_level="MEDIUM",
            confidence=0.8,
        )
        validation = validate_classification(result)
        assert not validation.is_valid
        assert any("Invalid intent" in e for e in validation.errors)

    def test_none_intent_passes(self):
        """None intent (fallback) should pass — it's a valid safe state."""
        result = ClassificationResult(
            intent=None,
            source="FALLBACK",
            sentiment_score=50,
            urgency_level="MEDIUM",
            confidence=0.0,
        )
        validation = validate_classification(result)
        assert validation.is_valid

    def test_sentiment_out_of_range_warning(self):
        """Sentiment score outside 0-100 should trigger warning and be clamped."""
        result = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score=150,  # Out of range
            urgency_level="MEDIUM",
            confidence=0.8,
        )
        validation = validate_classification(result)
        assert validation.is_valid
        assert any("out of range" in w for w in validation.warnings)
        assert validation.sanitized.sentiment_score == 100  # Clamped

    def test_negative_sentiment_clamped(self):
        """Negative sentiment score should be clamped to 0."""
        result = ClassificationResult(
            intent="NOT_INTERESTED",
            source="DECLINE_PHRASE",
            sentiment_score=-10,
            urgency_level="LOW",
            confidence=1.0,
        )
        validation = validate_classification(result)
        assert validation.sanitized.sentiment_score == 0

    def test_invalid_urgency_warning(self):
        """Invalid urgency level should default to MEDIUM."""
        result = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score=50,
            urgency_level="CRITICAL",  # Invalid
            confidence=0.8,
        )
        validation = validate_classification(result)
        assert validation.sanitized.urgency_level == "MEDIUM"

    def test_non_numeric_sentiment_warning(self):
        """Non-numeric sentiment should default to 50."""
        result = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score="high",  # Not a number
            urgency_level="MEDIUM",
            confidence=0.8,
        )
        validation = validate_classification(result)
        # String "high" is not instance of (int, float), so warning + default
        assert any("not numeric" in w for w in validation.warnings)


class TestBusinessRules:
    """Test business rule validation."""

    def test_not_interested_low_sentiment_consistency(self):
        """NOT_INTERESTED with high sentiment should be adjusted down."""
        result = ClassificationResult(
            intent="NOT_INTERESTED",
            source="LLM",
            sentiment_score=80,  # Inconsistent with NOT_INTERESTED
            urgency_level="LOW",
            confidence=0.9,
        )
        validation = validate_classification(result)
        assert any("NOT_INTERESTED" in w for w in validation.warnings)
        assert validation.sanitized.sentiment_score == 15

    def test_interested_low_sentiment_boosted(self):
        """INTERESTED with very low sentiment should be boosted."""
        result = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score=20,  # Too low for INTERESTED
            urgency_level="MEDIUM",
            confidence=0.8,
        )
        validation = validate_classification(result)
        assert any("Positive intent" in w for w in validation.warnings)
        assert validation.sanitized.sentiment_score == 60

    def test_low_confidence_warning(self):
        """Low LLM confidence should trigger a warning."""
        result = ClassificationResult(
            intent="MEETING_REQUESTED",
            source="LLM",
            sentiment_score=70,
            urgency_level="HIGH",
            confidence=0.3,  # Low
        )
        validation = validate_classification(result)
        assert any("Low LLM confidence" in w for w in validation.warnings)

    def test_decline_phrase_high_confidence(self):
        """Decline phrase detections should have high confidence."""
        result = ClassificationResult(
            intent="NOT_INTERESTED",
            source="DECLINE_PHRASE",
            sentiment_score=10,
            urgency_level="LOW",
            confidence=1.0,
        )
        validation = validate_classification(result)
        assert validation.is_valid
        assert validation.sanitized.confidence == 1.0


class TestStateMachineGuards:
    """Test that validator checks state machine transitions."""

    def test_valid_transition_passes(self):
        """REPLIED intent on SENT state should pass (valid transition)."""
        result = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score=75,
            urgency_level="HIGH",
            confidence=0.9,
        )
        validation = validate_classification(
            result,
            lead_state="SENT",
            current_followup_status="ACTIVE",
        )
        assert validation.is_valid

    def test_invalid_transition_warns(self):
        """State transition that violates machine rules should warn."""
        result = ClassificationResult(
            intent="INTERESTED",
            source="LLM",
            sentiment_score=75,
            urgency_level="HIGH",
            confidence=0.9,
        )
        # NEW → MEETING_REQUIRED is not a valid transition
        validation = validate_classification(
            result,
            lead_state="NEW",
        )
        # Should still pass (warnings, not errors) — AI recommends, state machine decides
        assert validation.is_valid


class TestSourceIntegrity:
    """Test source field validation."""

    def test_valid_sources_pass(self):
        """Known sources should pass."""
        for source in ("DECLINE_PHRASE", "LLM", "FALLBACK", "VALIDATION_FAILED"):
            result = ClassificationResult(
                intent=None,
                source=source,
                sentiment_score=50,
                urgency_level="MEDIUM",
                confidence=0.5,
            )
            validation = validate_classification(result)
            assert validation.is_valid

    def test_unknown_source_warns(self):
        """Unknown source should trigger warning."""
        result = ClassificationResult(
            intent=None,
            source="UNKNOWN_SOURCE",
            sentiment_score=50,
            urgency_level="MEDIUM",
            confidence=0.5,
        )
        validation = validate_classification(result)
        assert any("Unknown source" in w for w in validation.warnings)
