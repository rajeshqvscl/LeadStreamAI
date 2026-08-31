"""
Unit tests for click tracking (inject_click_tracking, _make_unique_gif, _is_safe_redirect_url).
Pure logic — no DB, no network.
"""

import pytest

from app.api.tracking import inject_click_tracking, _make_unique_gif, _is_safe_redirect_url


class TestInjectClickTracking:
    """Replace href links with tracking redirect URLs."""

    def test_replaces_href_links(self):
        html = '<a href="https://example.com">Click here</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert "api/track/click/tok123" in result
        assert "example.com" in result

    def test_preserves_visible_text(self):
        html = '<a href="https://example.com">Click here</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert "Click here" in result

    def test_skips_mailto(self):
        html = '<a href="mailto:test@example.com">Email</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert "mailto:" in result
        assert "api/track" not in result

    def test_skips_tel(self):
        html = '<a href="tel:+1234567890">Call</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert "tel:" in result
        assert "api/track" not in result

    def test_skips_anchor(self):
        html = '<a href="#section">Jump</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert 'href="#section"' in result
        assert "api/track" not in result

    def test_skips_javascript(self):
        html = '<a href="javascript:void(0)">Bad</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert "javascript:" in result
        assert "api/track" not in result

    def test_skips_already_tracked(self):
        html = '<a href="http://localhost:8000/api/track/click/tok123?url=test">Link</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert result.count("api/track/click") == 1

    def test_skips_unsubscribe(self):
        html = '<a href="http://localhost:8000/unsubscribe?token=abc">Unsub</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert "unsubscribe" in result
        assert result.count("api/track") == 0

    def test_none_input_returns_none(self):
        result = inject_click_tracking(None, "tok123", "http://localhost:8000")
        assert result is None

    def test_empty_input_returns_empty(self):
        result = inject_click_tracking("", "tok123", "http://localhost:8000")
        assert result == ""

    def test_no_tracking_token_returns_unchanged(self):
        html = '<a href="https://example.com">Link</a>'
        result = inject_click_tracking(html, "", "http://localhost:8000")
        assert result == html

    def test_single_quotes_in_href(self):
        html = "<a href='https://example.com'>Link</a>"
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert "api/track/click/tok123" in result

    def test_multiple_links(self):
        html = '<a href="https://a.com">A</a> <a href="https://b.com">B</a>'
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert result.count("api/track/click/tok123") == 2

    def test_no_links_unchanged(self):
        html = "<p>No links here</p>"
        result = inject_click_tracking(html, "tok123", "http://localhost:8000")
        assert result == html


class TestMakeUniqueGif:
    """_make_unique_gif produces valid GIF bytes."""

    def test_returns_valid_gif(self):
        gif = _make_unique_gif("test_seed")
        assert isinstance(gif, bytes)
        assert gif[:6] == b"GIF89a"

    def test_different_seeds_different_bytes(self):
        gif1 = _make_unique_gif("seed_a")
        gif2 = _make_unique_gif("seed_b")
        assert gif1 != gif2

    def test_same_seed_same_bytes(self):
        gif1 = _make_unique_gif("same_seed")
        gif2 = _make_unique_gif("same_seed")
        assert gif1 == gif2

    def test_length_is_fixed(self):
        gif1 = _make_unique_gif("a")
        gif2 = _make_unique_gif("b")
        assert len(gif1) == len(gif2)


class TestIsSafeRedirectUrl:
    """URL safety validation for redirects."""

    def test_relative_path_allowed(self):
        assert _is_safe_redirect_url("/dashboard") is True

    def test_relative_deep_path_allowed(self):
        assert _is_safe_redirect_url("/api/v1/leads") is True

    def test_allowed_host_leadstreamai(self):
        assert _is_safe_redirect_url("https://leadstreamai.onrender.com/page") is True

    def test_allowed_host_lead_backend(self):
        assert _is_safe_redirect_url("http://lead-backend-g9de.onrender.com/api") is True

    def test_allowed_host_localhost(self):
        assert _is_safe_redirect_url("http://localhost:3000/page") is True

    def test_unknown_host_blocked(self):
        assert _is_safe_redirect_url("https://evil.com/phish") is False

    def test_javascript_blocked(self):
        assert _is_safe_redirect_url("javascript:alert(1)") is False

    def test_protocol_relative_blocked(self):
        assert _is_safe_redirect_url("//evil.com/path") is False

    def test_data_uri_blocked(self):
        assert _is_safe_redirect_url("data:text/html,<script>alert(1)</script>") is False

    def test_empty_string_blocked(self):
        assert _is_safe_redirect_url("") is False

    def test_none_blocked(self):
        assert _is_safe_redirect_url(None) is False

    def test_case_insensitive(self):
        assert _is_safe_redirect_url("HTTPS://LEADSTREAMAI.ONRENDER.COM/page") is True
