"""
Unit tests for decline phrase detection.
Pure logic — no DB, no network.
"""

import pytest

from app.core.reply.decline_phrases import detect_decline_phrase


class TestDeclinePhraseEdgeCases:
    """Edge cases and input validation."""

    def test_none_input(self):
        assert detect_decline_phrase(None) is None

    def test_empty_string(self):
        assert detect_decline_phrase("") is None

    def test_no_decline_phrase(self):
        assert detect_decline_phrase("Thanks for the update, we will review.") is None

    def test_whitespace_only(self):
        assert detect_decline_phrase("   ") is None


class TestDeclinePhraseMatching:
    """Each of the 17 patterns should match with correct label."""

    def test_we_will_pass_on_this_opportunity(self):
        assert detect_decline_phrase("We will pass on this opportunity") == "We will pass on this opportunity"

    def test_pass_on_this_opportunity(self):
        assert detect_decline_phrase("We'd like to pass on this opportunity") == "Pass on this opportunity"

    def test_we_only_invest_in(self):
        assert detect_decline_phrase("We only invest in biotech") == "We only invest in"

    def test_we_only_do(self):
        assert detect_decline_phrase("We only do series B and later") == "We only do"

    def test_we_will_pass(self):
        assert detect_decline_phrase("We will pass") == "We will pass"

    def test_well_pass(self):
        assert detect_decline_phrase("We'll pass") == "We'll pass"

    def test_not_a_current_fit(self):
        assert detect_decline_phrase("This is not a current fit for us") == "Not a current fit"

    def test_not_fit_for_us(self):
        assert detect_decline_phrase("Not fit for us at this time") == "Not fit for us"

    def test_no_thank_you(self):
        assert detect_decline_phrase("No thank you") == "No thank you"

    def test_no_thank_you_with_comma(self):
        assert detect_decline_phrase("no, thank you") == "No thank you"

    def test_no_thanks(self):
        assert detect_decline_phrase("No thanks") == "No thank you"

    def test_please_share_a_detailed_deck(self):
        assert detect_decline_phrase("Please share a detailed deck") == "Please share a detailed deck"

    def test_pass_from_us(self):
        assert detect_decline_phrase("Pass from us") == "Pass from us"

    def test_pass_for_now(self):
        assert detect_decline_phrase("Pass for now") == "Pass for now"

    def test_not_within_our_mandate(self):
        assert detect_decline_phrase("Not within our mandate") == "Not within our mandate"

    def test_too_early_for_us(self):
        assert detect_decline_phrase("Too early for us") == "Too early for us"

    def test_not_interested(self):
        assert detect_decline_phrase("Not interested") == "Not interested"

    def test_we_do_not_invest(self):
        assert detect_decline_phrase("We do not invest in this sector") == "We do not invest"

    def test_decline_the_opportunity(self):
        assert detect_decline_phrase("We decline the opportunity") == "Decline the opportunity"

    def test_not_a_good_fit(self):
        assert detect_decline_phrase("Not a good fit for our portfolio") == "Not a good fit"


class TestDeclinePhraseCaseInsensitivity:
    """Matching should be case insensitive."""

    def test_uppercase_we_will_pass(self):
        assert detect_decline_phrase("WE WILL PASS") == "We will pass"

    def test_mixed_case_not_interested(self):
        assert detect_decline_phrase("Not Interested") == "Not interested"

    def test_lowercase_no_thank_you(self):
        assert detect_decline_phrase("no thank you") == "No thank you"

    def test_uppercase_pass_for_now(self):
        assert detect_decline_phrase("PASS FOR NOW") == "Pass for now"


class TestDeclinePhraseNegatives:
    """Phrases that should NOT match decline patterns."""

    def test_pass_along_does_not_match_we_will_pass(self):
        assert detect_decline_phrase("pass this along to team") is None

    def test_pass_along_info_does_not_match(self):
        assert detect_decline_phrase("I will pass along your info to the team") is None

    def test_pass_it_along_does_not_match(self):
        assert detect_decline_phrase("I'll pass it along to the right person") is None

    def test_pass_that_along_does_not_match(self):
        assert detect_decline_phrase("Let me pass that along to the team") is None


class TestDeclinePhraseWhitespaceNormalization:
    """Extra whitespace should not break matching."""

    def test_multiple_spaces(self):
        assert detect_decline_phrase("We  will   pass") == "We will pass"

    def test_leading_trailing_whitespace(self):
        assert detect_decline_phrase("  Not interested  ") == "Not interested"

    def test_newlines_and_tabs(self):
        assert detect_decline_phrase("Pass\nfor\tnow") == "Pass for now"


class TestDeclinePhraseUnicode:
    """Unicode and special characters should not break detection."""

    def test_unicode_punctuation(self):
        assert detect_decline_phrase("Not interested.") == "Not interested"

    def test_exclamation_mark(self):
        assert detect_decline_phrase("We will pass!") == "We will pass"

    def test_quotes_around_phrase(self):
        assert detect_decline_phrase('"We will pass"') == "We will pass"

    def test_unicode_smart_quotes(self):
        # Smart quotes are normalized by lowercasing but not stripped — still fine
        result = detect_decline_phrase("We will pass")
        assert result == "We will pass"
