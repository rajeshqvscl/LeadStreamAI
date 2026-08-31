"""
Unit tests for template engine filters:
  format_currency_filter, truncate_words_filter, markdownify_filter
Pure logic — no DB, no network.
"""

import pytest

from app.email_engine.template.engine import (
    format_currency_filter,
    markdownify_filter,
    truncate_words_filter,
)


class TestFormatCurrencyFilter:
    """Tests for format_currency_filter."""

    def test_one_crore(self):
        assert format_currency_filter(1e7) == "₹1.00 Cr"

    def test_five_crore(self):
        assert format_currency_filter(5e7) == "₹5.00 Cr"

    def test_one_lakh(self):
        assert format_currency_filter(1e5) == "₹1.00 L"

    def test_five_lakh(self):
        assert format_currency_filter(5e5) == "₹5.00 L"

    def test_small_number(self):
        assert format_currency_filter(1234) == "₹1,234"

    def test_none_returns_empty(self):
        assert format_currency_filter(None) == ""

    def test_non_numeric_string_returns_as_is(self):
        assert format_currency_filter("abc") == "abc"

    def test_zero(self):
        assert format_currency_filter(0) == "₹0"

    def test_string_number(self):
        assert format_currency_filter("500000") == "₹5.00 L"


class TestTruncateWordsFilter:
    """Tests for truncate_words_filter."""

    def test_truncate_to_3_words(self):
        assert truncate_words_filter("a b c d e", 3) == "a b c..."

    def test_short_text_not_truncated(self):
        assert truncate_words_filter("short", 10) == "short"

    def test_empty_string(self):
        assert truncate_words_filter("", 5) == ""

    def test_none_returns_empty(self):
        assert truncate_words_filter(None, 5) == ""

    def test_exact_word_count(self):
        assert truncate_words_filter("a b c", 3) == "a b c"

    def test_single_word(self):
        assert truncate_words_filter("hello", 1) == "hello"

    def test_default_length_50(self):
        text = " ".join(["word"] * 60)
        result = truncate_words_filter(text)
        assert result.endswith("...")
        # 50 words: the last word has "..." appended, so split() gives 50 tokens
        assert len(result.split()) == 50


class TestMarkdownifyFilter:
    """Tests for markdownify_filter."""

    def test_heading(self):
        assert "<h2>Hello</h2>" in markdownify_filter("## Hello")

    def test_bold(self):
        result = markdownify_filter("**bold**")
        assert "<strong>bold</strong>" in result

    def test_paragraph(self):
        result = markdownify_filter("Hello world")
        assert "<p>Hello world</p>" in result

    def test_list(self):
        result = markdownify_filter("- item 1\n- item 2")
        assert "<ul>" in result
        assert "item 1" in result


# Run with: pytest tests/unit/test_template_filters.py -v
