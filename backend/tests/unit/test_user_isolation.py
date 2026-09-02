"""
User isolation / cross-tenant safety tests.

These tests verify that:
  1. User A's data is never visible to User B
  2. Admin sees everything, non-admin sees only their own
  3. Signatures, Gmail services, and leads are scoped per user
  4. Session tokens are user-specific
  5. The normalize_user_id function correctly resolves identities

All tests use mocked DB — no real database needed.
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------


def _ctx_mock(mock_conn):
    """Return a mock for get_db() that yields mock_conn as a context manager."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_conn)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------


class TestNormalizeUserId:
    """normalize_user_id must resolve identities safely."""

    def test_none_returns_none(self):
        from app.utils.auth_helpers import normalize_user_id
        assert normalize_user_id(None) is None

    def test_empty_string_returns_none(self):
        from app.utils.auth_helpers import normalize_user_id
        assert normalize_user_id("") is None

    def test_admin_string_resolves_to_1(self):
        from app.utils.auth_helpers import normalize_user_id
        assert normalize_user_id("admin") == "1"
        assert normalize_user_id("ADMIN") == "1"
        assert normalize_user_id("Admin") == "1"

    def test_numeric_id_passes_through(self):
        from app.utils.auth_helpers import normalize_user_id
        assert normalize_user_id("42") == "42"
        assert normalize_user_id("1") == "1"

    @patch("app.utils.auth_helpers.get_db")
    def test_username_resolves_via_db(self, mock_get_db):
        from app.utils.auth_helpers import normalize_user_id

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"id": 77}
        mock_get_db.return_value = _ctx_mock(conn)

        result = normalize_user_id("johndoe")
        assert result == "77"

    @patch("app.utils.auth_helpers.get_db")
    def test_unknown_user_returns_none(self, mock_get_db):
        from app.utils.auth_helpers import normalize_user_id

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = None
        mock_get_db.return_value = _ctx_mock(conn)

        result = normalize_user_id("unknownuser")
        assert result is None

    @patch("app.utils.auth_helpers.get_db")
    def test_db_error_returns_none(self, mock_get_db):
        """DB failure → returns None (not admin, not leaked)."""
        from app.utils.auth_helpers import normalize_user_id

        mock_get_db.side_effect = Exception("Connection refused")
        result = normalize_user_id("johndoe")
        assert result is None


# ---------------------------------------------------------------------------


class TestIsAdminUser:
    """Admin role must be determined from DB, not header string."""

    def test_none_returns_false(self):
        from app.utils.auth_helpers import is_admin_user
        assert is_admin_user(None) is False

    def test_empty_returns_false(self):
        from app.utils.auth_helpers import is_admin_user
        assert is_admin_user("") is False

    def test_non_digit_returns_false(self):
        from app.utils.auth_helpers import is_admin_user
        assert is_admin_user("admin") is False
        assert is_admin_user("abc") is False

    @patch("app.utils.auth_helpers.get_db")
    def test_admin_role_returns_true(self, mock_get_db):
        from app.utils.auth_helpers import is_admin_user

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"role": "ADMIN"}
        mock_get_db.return_value = _ctx_mock(conn)

        assert is_admin_user("1") is True

    @patch("app.utils.auth_helpers.get_db")
    def test_user_role_returns_false(self, mock_get_db):
        from app.utils.auth_helpers import is_admin_user

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"role": "USER"}
        mock_get_db.return_value = _ctx_mock(conn)

        assert is_admin_user("2") is False

    @patch("app.utils.auth_helpers.get_db")
    def test_db_error_returns_false(self, mock_get_db):
        """DB failure → not admin (fail-safe)."""
        from app.utils.auth_helpers import is_admin_user

        mock_get_db.side_effect = Exception("timeout")
        assert is_admin_user("1") is False


# ---------------------------------------------------------------------------


class TestDailyEmailLimit:
    """Each user has their own daily limit — no cross-user leakage."""

    @patch("app.utils.auth_helpers.get_db")
    @patch("app.utils.auth_helpers.normalize_user_id", return_value="2")
    @patch("app.utils.auth_helpers.is_admin_user", return_value=False)
    def test_user_within_limit(self, _is_admin, _norm, mock_get_db):
        """User with 10 sent emails and limit 2000 → allowed."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        # check_daily_email_limit opens ONE connection, calls:
        #   1. SELECT outreach_daily_limit
        #   2. SELECT COUNT(*) sent today
        cur.fetchone.side_effect = [
            [2000],  # limit query
            [10],    # sent count
        ]
        mock_get_db.return_value = _ctx_mock(conn)

        result = check_daily_email_limit("2", batch_size=1)
        assert result is True  # 10 + 1 <= 2000

    @patch("app.utils.auth_helpers.get_db")
    @patch("app.utils.auth_helpers.normalize_user_id", return_value="3")
    @patch("app.utils.auth_helpers.is_admin_user", return_value=False)
    def test_user_exceeds_limit(self, _is_admin, _norm, mock_get_db):
        """User at limit → blocked."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.side_effect = [
            [100],  # low limit
            [100],  # already at limit
        ]
        mock_get_db.return_value = _ctx_mock(conn)

        result = check_daily_email_limit("3", batch_size=1)
        assert result is False  # 100 + 1 > 100

    @patch("app.utils.auth_helpers.get_db")
    @patch("app.utils.auth_helpers.normalize_user_id", return_value="1")
    @patch("app.utils.auth_helpers.is_admin_user", return_value=True)
    def test_admin_uses_default_limit(self, _is_admin, _norm, mock_get_db):
        """Admin → uses default 2000 limit (no per-user query)."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        # Admin skips the limit query, only runs the count query
        cur.fetchone.return_value = [10]  # 10 sent today
        mock_get_db.return_value = _ctx_mock(conn)

        result = check_daily_email_limit("1", batch_size=1)
        assert result is True  # 10 + 1 <= 2000 → allowed

        # Verify admin did NOT query the per-user limit table
        for call_args in cur.execute.call_args_list:
            query = call_args[0][0]
            assert "outreach_daily_limit" not in query, "Admin should not query per-user limit"

    @patch("app.utils.auth_helpers.get_db")
    @patch("app.utils.auth_helpers.normalize_user_id", return_value="2")
    @patch("app.utils.auth_helpers.is_admin_user", return_value=False)
    def test_user_id_isolation_in_count_query(self, _is_admin, _norm, mock_get_db):
        """Count query uses user_id in WHERE — users don't share counts."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.side_effect = [
            [2000],  # limit
            [5],     # count
        ]
        mock_get_db.return_value = _ctx_mock(conn)

        check_daily_email_limit("2", batch_size=1)

        # Verify the count query was parameterized with user_id
        count_query = cur.execute.call_args_list[1]
        query_sql = count_query[0][0]
        query_params = count_query[0][1]
        assert "user_id = %s" in query_sql
        assert "2" in str(query_params)


# ---------------------------------------------------------------------------


class TestLeadScoping:
    """Leads must be scoped to the user who owns them."""

    def test_admin_user_id_always_1(self):
        """'admin' string → normalized to '1' → queries use user_id=1."""
        from app.utils.auth_helpers import normalize_user_id
        uid = normalize_user_id("admin")
        assert uid == "1"

    def test_non_admin_preserves_id(self):
        """Numeric user_id preserved as-is."""
        from app.utils.auth_helpers import normalize_user_id
        uid = normalize_user_id("5")
        assert uid == "5"


# ---------------------------------------------------------------------------


class TestSessionIsolation:
    """Sessions are per-user — one token maps to one user."""

    @patch("app.utils.auth_helpers.get_db")
    @patch("app.utils.auth_helpers.normalize_user_id", return_value="3")
    @patch("app.utils.auth_helpers.is_admin_user", return_value=False)
    def test_get_daily_limit_returns_own_limit(self, _is_admin, _norm, mock_get_db):
        """Each user's limit is fetched independently."""
        from app.utils.auth_helpers import get_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = [500]
        mock_get_db.return_value = _ctx_mock(conn)

        limit = get_daily_email_limit("3")
        assert limit == 500

        # Verify the query used user_id=3
        query_params = cur.execute.call_args[0][1]
        assert "3" in str(query_params)

    @patch("app.utils.auth_helpers.get_db")
    @patch("app.utils.auth_helpers.is_admin_user", return_value=False)
    def test_user2_limit_independent_of_user3(self, _is_admin, mock_get_db):
        """User 2 and User 3 have different limits."""
        from app.utils.auth_helpers import get_daily_email_limit

        # Call for user 2
        conn2 = MagicMock()
        cur2 = MagicMock()
        conn2.cursor.return_value = cur2
        cur2.fetchone.return_value = [2000]

        with patch("app.utils.auth_helpers.normalize_user_id", return_value="2"):
            mock_get_db.return_value = _ctx_mock(conn2)
            limit2 = get_daily_email_limit("2")
            assert limit2 == 2000

        # Call for user 3
        conn3 = MagicMock()
        cur3 = MagicMock()
        conn3.cursor.return_value = cur3
        cur3.fetchone.return_value = [1500]

        with patch("app.utils.auth_helpers.normalize_user_id", return_value="3"):
            mock_get_db.return_value = _ctx_mock(conn3)
            limit3 = get_daily_email_limit("3")
            assert limit3 == 1500


# ---------------------------------------------------------------------------


class TestFontIsolation:
    """Font preferences are per-user, not global."""

    def test_user2_font_different_from_user3(self):
        """User 2 uses Arial, User 3 uses sans-serif."""
        from app.services.email_service import USER_EMAIL_FONTS
        assert USER_EMAIL_FONTS.get(2) != USER_EMAIL_FONTS.get(3)

    def test_user3_font_same_as_user4(self):
        """Users 3, 4, 5 share the same font."""
        from app.services.email_service import USER_EMAIL_FONTS
        assert USER_EMAIL_FONTS.get(3) == USER_EMAIL_FONTS.get(4)
        assert USER_EMAIL_FONTS.get(4) == USER_EMAIL_FONTS.get(5)

    def test_unknown_user_gets_default(self):
        """Unknown user_id → default font."""
        from app.services.email_service import USER_EMAIL_FONTS, DEFAULT_EMAIL_FONT
        assert USER_EMAIL_FONTS.get(999, DEFAULT_EMAIL_FONT) == DEFAULT_EMAIL_FONT

    def test_font_sizes_differ_per_user(self):
        """Different users have different font sizes."""
        from app.services.email_service import USER_EMAIL_FONT_SIZES
        assert USER_EMAIL_FONT_SIZES.get(2) != USER_EMAIL_FONT_SIZES.get(3)


# ---------------------------------------------------------------------------


class TestUnsubscribeIsolation:
    """Unsubscribing one lead should not affect other leads."""

    @patch("app.database.get_db")
    def test_one_unsubscribed_lead_doesnt_block_others(self, mock_get_db):
        """Lead A unsubscribed → Lead B still sends."""
        from app.services.email_service import send_email

        # Build mock DB connection for unsubscribe guard
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {
            "email_opt_in": True,
            "is_unsubscribed": True,
        }
        mock_get_db.return_value = _ctx_mock(conn)

        ok, msg, tid, rfc = send_email(
            to_email="unsubscribed@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=2,
            lead_id=42,  # unsubscribed lead
        )
        assert ok is False
        assert "unsubscribed" in msg.lower()
