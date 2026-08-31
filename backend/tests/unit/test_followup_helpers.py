"""
Unit tests for followup_service.is_generic_followup()
Pure regex / string logic — no DB, no network.
"""

import pytest

from app.services.followup_service import is_generic_followup


class TestIsGenericFollowup:
    """Tests for is_generic_followup function."""

    def test_none_returns_true(self):
        assert is_generic_followup(None) is True

    def test_empty_string_returns_true(self):
        assert is_generic_followup("") is True

    def test_whitespace_only_returns_true(self):
        assert is_generic_followup("   ") is True

    def test_empty_html_returns_true(self):
        assert is_generic_followup("<p></p>") is True

    def test_generic_previous_email(self):
        assert is_generic_followup("Just following up on my previous email.") is True

    def test_generic_hi_following_up_with_questions(self):
        assert is_generic_followup("Hi, following up. Any questions?") is True

    def test_generic_let_me_know_questions_without_following_up(self):
        assert is_generic_followup("Please let me know if you have any questions.") is False

    def test_generic_following_up_with_previous_email(self):
        assert is_generic_followup("Hi, following up on my previous email.") is True

    def test_specific_content_not_generic(self):
        assert is_generic_followup("I'd like to discuss the Series B round.") is False

    def test_specific_revenue_not_generic(self):
        assert is_generic_followup("Our platform raised $2M last quarter.") is False

    def test_html_wrapped_generic(self):
        assert is_generic_followup("<p>Following up on my previous email.</p>") is True

    def test_subject_line_marks_original(self):
        assert is_generic_followup("Subject: Investment Opportunity\n\nHi, ...") is True


# Run with: pytest tests/unit/test_followup_helpers.py -v
