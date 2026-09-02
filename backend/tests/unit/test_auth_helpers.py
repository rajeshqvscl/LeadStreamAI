"""
Unit tests for auth_helpers (normalize_user_id, is_admin_user)
Only tests pure / hardcoded paths — skips or mocks DB calls.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.utils.auth_helpers import is_admin_user, normalize_user_id


def _mock_get_db(mock_conn):
    """Return a mock for get_db() that yields mock_conn as a context manager."""
    @contextmanager
    def _ctx():
        yield mock_conn
    return MagicMock(side_effect=_ctx)


class TestNormalizeUserId:
    """Tests for normalize_user_id — pure paths only."""

    def test_none_returns_none(self):
        assert normalize_user_id(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_user_id("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_user_id("   ") is None

    def test_admin_lowercase_returns_1(self):
        assert normalize_user_id("admin") == "1"

    def test_admin_uppercase_returns_1(self):
        assert normalize_user_id("ADMIN") == "1"

    def test_numeric_string_returns_itself(self):
        assert normalize_user_id("123") == "123"

    @patch("app.utils.auth_helpers.get_db")
    def test_username_resolves_via_db(self, mock_get_db):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {"id": 42}
        result = normalize_user_id("johndoe")
        assert result == "42"

    @patch("app.utils.auth_helpers.get_db")
    def test_unknown_user_returns_none(self, mock_get_db):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        result = normalize_user_id("unknownuser")
        assert result is None

    @patch("app.utils.auth_helpers.get_db")
    def test_db_error_returns_none(self, mock_get_db):
        """DB failure → returns None (not admin, not leaked)."""
        mock_get_db.side_effect = Exception("Connection refused")
        result = normalize_user_id("johndoe")
        assert result is None


class TestIsAdminUser:
    """Tests for is_admin_user — pure paths only."""

    def test_none_returns_false(self):
        assert is_admin_user(None) is False

    def test_empty_string_returns_false(self):
        assert is_admin_user("") is False

    def test_non_digit_string_returns_false(self):
        assert is_admin_user("abc") is False

    @patch("app.utils.auth_helpers.get_db")
    def test_digit_id_queries_db_for_role(self, mock_get_db):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {"role": "ADMIN"}
        result = is_admin_user("123")
        assert result is True

    @patch("app.utils.auth_helpers.get_db")
    def test_digit_id_non_admin_returns_false(self, mock_get_db):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {"role": "USER"}
        result = is_admin_user("456")
        assert result is False

    @patch("app.utils.auth_helpers.get_db")
    def test_digit_id_no_user_returns_false(self, mock_get_db):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        result = is_admin_user("999")
        assert result is False

    @patch("app.utils.auth_helpers.get_db")
    def test_db_error_returns_false(self, mock_get_db):
        """DB failure → not admin (fail-safe)."""
        mock_get_db.side_effect = Exception("timeout")
        assert is_admin_user("1") is False


# Run with: pytest tests/unit/test_auth_helpers.py -v
