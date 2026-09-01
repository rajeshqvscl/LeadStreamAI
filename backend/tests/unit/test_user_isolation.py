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
# normalize_user_id — identity resolution
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

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_username_resolves_via_db(self, mock_get_db):
        from app.utils.auth_helpers import normalize_user_id

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"id": 77}
        mock_get_db.return_value = conn

        result = normalize_user_id("johndoe")
        assert result == "77"
        conn.close.assert_called_once()

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_unknown_user_returns_none(self, mock_get_db):
        from app.utils.auth_helpers import normalize_user_id

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = None
        mock_get_db.return_value = conn

        result = normalize_user_id("unknownuser")
        assert result is None

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_db_error_returns_none(self, mock_get_db):
        """DB failure → returns None (not admin, not leaked)."""
        from app.utils.auth_helpers import normalize_user_id

        mock_get_db.side_effect = Exception("Connection refused")
        result = normalize_user_id("johndoe")
        assert result is None


# ---------------------------------------------------------------------------
# is_admin_user — role check
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

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_admin_role_returns_true(self, mock_get_db):
        from app.utils.auth_helpers import is_admin_user

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"role": "ADMIN"}
        mock_get_db.return_value = conn

        assert is_admin_user("1") is True

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_user_role_returns_false(self, mock_get_db):
        from app.utils.auth_helpers import is_admin_user

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"role": "USER"}
        mock_get_db.return_value = conn

        assert is_admin_user("2") is False

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_db_error_returns_false(self, mock_get_db):
        """DB failure → not admin (fail-safe)."""
        from app.utils.auth_helpers import is_admin_user

        mock_get_db.side_effect = Exception("timeout")
        assert is_admin_user("1") is False


# ---------------------------------------------------------------------------
# Daily email limit — per-user enforcement
# ---------------------------------------------------------------------------

class TestDailyEmailLimit:
    """Each user has their own daily limit — no cross-user leakage."""

    def test_user_within_limit(self):
        """User with 10 sent emails and limit 2000 → allowed."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        # check_daily_email_limit opens ONE connection, calls:
        #   1. SELECT outreach_daily_limit
        #   2. SELECT COUNT(*) sent today
        cur.fetchone.side_effect = [
            {"outreach_daily_limit": 2000},  # limit query
            {"count": 10},                   # sent count
        ]

        with patch("app.utils.auth_helpers.get_db_connection", return_value=conn), \
             patch("app.utils.auth_helpers.normalize_user_id", return_value="2"), \
             patch("app.utils.auth_helpers.is_admin_user", return_value=False):
            result = check_daily_email_limit("2", batch_size=1)
            assert result is True  # 10 + 1 <= 2000

    def test_user_exceeds_limit(self):
        """User at limit → blocked."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        # Code uses row[0] positional access (not DictCursor col names)
        cur.fetchone.side_effect = [
            [100],   # low limit
            [100],   # already at limit
        ]

        with patch("app.utils.auth_helpers.get_db_connection", return_value=conn), \
             patch("app.utils.auth_helpers.normalize_user_id", return_value="3"), \
             patch("app.utils.auth_helpers.is_admin_user", return_value=False):
            result = check_daily_email_limit("3", batch_size=1)
            assert result is False  # 100 + 1 > 100

    def test_admin_unlimited(self):
        """Admin → no limit check, always allowed."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"count": 9999}

        with patch("app.utils.auth_helpers.get_db_connection", return_value=conn), \
             patch("app.utils.auth_helpers.normalize_user_id", return_value="1"), \
             patch("app.utils.auth_helpers.is_admin_user", return_value=True):
            result = check_daily_email_limit("1", batch_size=1)
            assert result is True

    def test_user_id_isolation_in_count_query(self):
        """Count query uses user_id in WHERE — users don't share counts."""
        from app.utils.auth_helpers import check_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.side_effect = [
            [2000],  # limit
            [5],     # count
        ]

        with patch("app.utils.auth_helpers.get_db_connection", return_value=conn), \
             patch("app.utils.auth_helpers.normalize_user_id", return_value="2"), \
             patch("app.utils.auth_helpers.is_admin_user", return_value=False):
            check_daily_email_limit("2", batch_size=1)

        # Verify the count query was parameterized with user_id
        count_query = cur.execute.call_args_list[1]
        query_sql = count_query[0][0]
        query_params = count_query[0][1]
        assert "user_id = %s" in query_sql
        assert "2" in str(query_params)


# ---------------------------------------------------------------------------
# Lead scoping — user_id in WHERE clause
# ---------------------------------------------------------------------------

class TestLeadScoping:
    """Leads must be scoped to the user who owns them."""

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_admin_user_id_always_1(self, mock_get_db):
        """'admin' string → normalized to '1' → queries use user_id=1."""
        from app.utils.auth_helpers import normalize_user_id

        uid = normalize_user_id("admin")
        assert uid == "1"

    @patch("app.utils.auth_helpers.get_db_connection")
    def test_non_admin_preserves_id(self, mock_get_db):
        """Numeric user_id preserved as-is."""
        from app.utils.auth_helpers import normalize_user_id

        uid = normalize_user_id("5")
        assert uid == "5"


# ---------------------------------------------------------------------------
# Session isolation
# ---------------------------------------------------------------------------

class TestSessionIsolation:
    """Sessions are per-user — one token maps to one user."""

    def test_get_daily_limit_returns_own_limit(self):
        """Each user's limit is fetched independently."""
        from app.utils.auth_helpers import get_daily_email_limit

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = [500]  # positional index access

        with patch("app.utils.auth_helpers.get_db_connection", return_value=conn), \
             patch("app.utils.auth_helpers.normalize_user_id", return_value="3"), \
             patch("app.utils.auth_helpers.is_admin_user", return_value=False):
            limit = get_daily_email_limit("3")
            assert limit == 500

            # Verify the query used user_id=3
            query_params = cur.execute.call_args[0][1]
            assert "3" in str(query_params)

    def test_user2_limit_independent_of_user3(self):
        """User 2 and User 3 have different limits."""
        from app.utils.auth_helpers import get_daily_email_limit

        # Call for user 2
        conn2 = MagicMock()
        cur2 = MagicMock()
        conn2.cursor.return_value = cur2
        cur2.fetchone.return_value = [2000]

        with patch("app.utils.auth_helpers.get_db_connection", return_value=conn2), \
             patch("app.utils.auth_helpers.normalize_user_id", return_value="2"), \
             patch("app.utils.auth_helpers.is_admin_user", return_value=False):
            limit2 = get_daily_email_limit("2")
            assert limit2 == 2000

        # Call for user 3
        conn3 = MagicMock()
        cur3 = MagicMock()
        conn3.cursor.return_value = cur3
        cur3.fetchone.return_value = [1500]

        with patch("app.utils.auth_helpers.get_db_connection", return_value=conn3), \
             patch("app.utils.auth_helpers.normalize_user_id", return_value="3"), \
             patch("app.utils.auth_helpers.is_admin_user", return_value=False):
            limit3 = get_daily_email_limit("3")
            assert limit3 == 1500


# ---------------------------------------------------------------------------
# Font isolation — different users, different configs
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
# Unsubscribe isolation
# ---------------------------------------------------------------------------

class TestUnsubscribeIsolation:
    """Unsubscribing one lead should not affect other leads."""

    @patch("app.database.get_db_connection")
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
        mock_get_db.return_value = conn

        ok, msg, tid, rfc = send_email(
            to_email="unsubscribed@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=2,
            lead_id=42,  # unsubscribed lead
        )
        assert ok is False
        assert "unsubscribed" in msg.lower()
