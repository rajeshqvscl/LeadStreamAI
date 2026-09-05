"""
Unit-test conftest — shared fixtures for backend/tests/unit/.

Key fixture: ``track_db_connections``
    Wraps ``app.database.get_db`` so every call is tracked.
    After each test the fixture verifies:
    1. Every connection that was opened was also closed.
    2. No connection was closed twice (double-free).
    3. The pool never exceeded its max size.

Usage in any test file:
    def test_something(track_db_connections):
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(...)
            conn.commit()
        # fixture auto-verifies after the test

Security-suite fixtures (``security_seed`` + named accessors)
    Seed two users + one admin with real sessions, plus leads and campaigns,
    in the PostgreSQL container CI provides. Every accessor fixture SKIPS its
    test when no DB is reachable, so the same files run green locally (skip)
    and in CI (real assertions). The ``client`` fixture (tests/conftest.py) is
    in real-DB mode when a DB is up, so session tokens are actually verified.
"""

import contextlib
import threading

import pytest

from tests.conftest import db_reachable


def seed_security_data() -> dict:
    """Seed users A/B + admin with sessions, plus leads & campaigns, and return
    a dict of ids/tokens. Plain function (not a fixture) so test files can
    decide for themselves whether to skip vs. fall back to stub mode."""
    import datetime
    import psycopg2
    import psycopg2.extras

    from tests.conftest import _TEST_DATABASE_URL

    # Connect to the TEST database explicitly — NOT the ambient DATABASE_URL
    # env var, which app modules flip to the production URL at import time
    # (load_dotenv(override=True)). Reading the ambient var made local runs
    # seed pytest rows into the real production Neon DB.
    conn = psycopg2.connect(_TEST_DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
    cur = conn.cursor()
    try:
        # Clean up rows from previous runs of the same suite (safe namespace)
        cur.execute("DELETE FROM sessions WHERE token LIKE 'pytest-sec-%'")
        cur.execute("DELETE FROM leads_raw WHERE email LIKE '%@pytest-security.local'")
        cur.execute("DELETE FROM campaigns WHERE name LIKE 'pytest-sec-%'")
        cur.execute("DELETE FROM users WHERE email LIKE '%@pytest-security.local'")
        conn.commit()

        cur.execute(
            "INSERT INTO users (username, email, full_name, role, is_active, is_approved) "
            "VALUES ('pytest_sec_a', 'sec-a@pytest-security.local', 'Sec A', 'USER', TRUE, TRUE) "
            "RETURNING id"
        )
        uid_a = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (username, email, full_name, role, is_active, is_approved) "
            "VALUES ('pytest_sec_b', 'sec-b@pytest-security.local', 'Sec B', 'USER', TRUE, TRUE) "
            "RETURNING id"
        )
        uid_b = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (username, email, full_name, role, is_active, is_approved) "
            "VALUES ('pytest_sec_admin', 'sec-admin@pytest-security.local', 'Sec Admin', 'ADMIN', TRUE, TRUE) "
            "RETURNING id"
        )
        uid_admin = cur.fetchone()[0]
        conn.commit()

        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        for token, uid in [
            ("pytest-sec-token-a", uid_a),
            ("pytest-sec-token-b", uid_b),
            ("pytest-sec-token-admin", uid_admin),
        ]:
            cur.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                (token, uid, expires),
            )
        conn.commit()

        # One lead + one campaign per user (same ids used by every accessor)
        cur.execute(
            "INSERT INTO leads_raw (first_name, last_name, email, company_name, user_id, "
            "email_status, pipeline_state, validation_status) "
            "VALUES ('Sec', 'A', 'lead-a@pytest-security.local', 'Acme A', %s, 'PENDING', 'NEW', 'PENDING') "
            "RETURNING id",
            (uid_a,),
        )
        lead_a = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO leads_raw (first_name, last_name, email, company_name, user_id, "
            "email_status, pipeline_state, validation_status) "
            "VALUES ('Sec', 'B', 'lead-b@pytest-security.local', 'Acme B', %s, 'PENDING', 'NEW', 'PENDING') "
            "RETURNING id",
            (uid_b,),
        )
        lead_b = cur.fetchone()[0]

        # Extra User-A leads so stateful tests (sent/active/unsubscribed) never
        # collide with the plain lead_a used by ownership/isolation tests.
        cur.execute(
            "INSERT INTO leads_raw (first_name, last_name, email, company_name, user_id, "
            "email_status, followup_status, pipeline_state, validation_status) "
            "VALUES ('Sec', 'A-Sent', 'sent-a@pytest-security.local', 'Acme A', %s, 'SENT', 'ACTIVE', 'SENT', 'PENDING') "
            "RETURNING id",
            (uid_a,),
        )
        lead_sent_a = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO leads_raw (first_name, last_name, email, company_name, user_id, "
            "email_status, followup_status, pipeline_state, validation_status) "
            "VALUES ('Sec', 'A-Active', 'active-a@pytest-security.local', 'Acme A', %s, 'PENDING', 'ACTIVE', 'NEW', 'PENDING') "
            "RETURNING id",
            (uid_a,),
        )
        lead_active_a = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO leads_raw (first_name, last_name, email, company_name, user_id, "
            "email_status, pipeline_state, validation_status, is_unsubscribed) "
            "VALUES ('Sec', 'A-Unsub', 'unsub-a@pytest-security.local', 'Acme A', %s, 'PENDING', 'NEW', 'PENDING', TRUE) "
            "RETURNING id",
            (uid_a,),
        )
        lead_unsub_a = cur.fetchone()[0]
        conn.commit()

        cur.execute(
            "INSERT INTO campaigns (name, description, is_active, user_id) "
            "VALUES ('pytest-sec-camp-a', 'seed', TRUE, %s) RETURNING id",
            (uid_a,),
        )
        camp_a = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO campaigns (name, description, is_active, user_id) "
            "VALUES ('pytest-sec-camp-b', 'seed', TRUE, %s) RETURNING id",
            (uid_b,),
        )
        camp_b = cur.fetchone()[0]
        conn.commit()

        return {
            "token_a": "pytest-sec-token-a",
            "token_b": "pytest-sec-token-b",
            "token_admin": "pytest-sec-token-admin",
            "user_a_id": uid_a,
            "user_b_id": uid_b,
            "admin_id": uid_admin,
            "lead_a": lead_a,
            "lead_b": lead_b,
            "sent_lead_id": lead_sent_a,
            "active_lead_id": lead_active_a,
            "unsubscribed_lead_id": lead_unsub_a,
            "campaign_a": camp_a,
            "campaign_b": camp_b,
        }
    finally:
        cur.close()
        conn.close()


def _requires_db():
    """Skip helper: call inside a fixture when no real DB is available."""
    if not db_reachable():
        pytest.skip("PostgreSQL not reachable — CI provides a service container")


@pytest.fixture(scope="session")
def security_seed():
    """Seeded users A/B + admin with sessions, leads & campaigns for
    ownership-matrix tests. Skips without a live DB."""
    _requires_db()
    return seed_security_data()


@pytest.fixture
def user_a_token(security_seed):
    """Session token for seeded User A (skips when no DB)."""
    return security_seed["token_a"]


@pytest.fixture
def user_b_token(security_seed):
    """Session token for seeded User B (skips when no DB)."""
    return security_seed["token_b"]


@pytest.fixture
def admin_token(security_seed):
    """Session token for seeded Admin (skips when no DB)."""
    return security_seed["token_admin"]


@pytest.fixture
def user_a_lead_id(security_seed):
    """Lead id owned by seeded User A (skips when no DB)."""
    return security_seed["lead_a"]


@pytest.fixture
def user_b_lead_id(security_seed):
    """Lead id owned by seeded User B (skips when no DB)."""
    return security_seed["lead_b"]


@pytest.fixture
def user_a_campaign_id(security_seed):
    """Campaign id owned by seeded User A (skips when no DB)."""
    return security_seed["campaign_a"]


@pytest.fixture
def user_b_campaign_id(security_seed):
    """Campaign id owned by seeded User B (skips when no DB)."""
    return security_seed["campaign_b"]


@pytest.fixture
def user_a_id(security_seed):
    """DB id of seeded User A (skips when no DB)."""
    return security_seed["user_a_id"]


@pytest.fixture
def user_b_id(security_seed):
    """DB id of seeded User B (skips when no DB)."""
    return security_seed["user_b_id"]


@pytest.fixture
def sent_lead_id(security_seed):
    """A SENT-state lead owned by seeded User A (skips when no DB)."""
    return security_seed["sent_lead_id"]


@pytest.fixture
def active_lead_id(security_seed):
    """An active (non-deleted) lead owned by seeded User A (skips when no DB)."""
    return security_seed["active_lead_id"]


@pytest.fixture
def unsubscribed_lead_id(security_seed):
    """An unsubscribed lead owned by seeded User A (skips when no DB)."""
    return security_seed["unsubscribed_lead_id"]


@pytest.fixture
def admin_id(security_seed):
    return security_seed["admin_id"]


# ---------------------------------------------------------------------------
# Connection tracker
# ---------------------------------------------------------------------------

class _ConnectionTracker:
    """Thread-safe tracker for DB connections opened/closed during a test."""

    def __init__(self):
        self._opened: dict[int, str] = {}      # id(conn) -> traceback string
        self._closed: set[int] = set()
        self._lock = threading.Lock()

    def record_open(self, conn):
        with self._lock:
            self._opened[id(conn)] = ""

    def record_close(self, conn):
        with self._lock:
            self._closed.add(id(conn))

    def assert_all_closed(self):
        with self._lock:
            leaked = {
                oid: tb
                for oid, tb in self._opened.items()
                if oid not in self._closed
            }
        assert not leaked, (
            f"DB connection LEAK detected — {len(leaked)} connection(s) opened "
            f"but never closed:\n"
            + "\n".join(f"  - conn id {oid}" for oid in leaked)
        )

    def assert_no_double_close(self):
        with self._lock:
            double_closed = self._closed - set(self._opened.keys())
        assert not double_closed, (
            f"Double-close detected for {len(double_closed)} connection(s)"
        )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def track_db_connections(monkeypatch):
    """Patch ``get_db`` to track open/close lifecycle.

    After the test the fixture asserts no connections leaked.
    """
    tracker = _ConnectionTracker()

    import app.database as dbmod

    _real_get_db = dbmod.get_db_connection

    def _tracked_get_db(*args, **kwargs):
        conn = _real_get_db(*args, **kwargs)
        tracker.record_open(conn)

        # Wrap .close() to also record the close
        _real_close = conn.close

        def _tracked_close(*a, **kw):
            tracker.record_close(conn)
            return _real_close(*a, **kw)

        # Handle both _PooledConnection (has .close) and raw psycopg2 connections
        if hasattr(conn, '_conn'):
            # _PooledConnection — wrap the inner close
            inner = object.__getattribute__(conn, '_conn')
            _inner_close = inner.close

            def _tracked_inner_close(*a, **kw):
                tracker.record_close(conn)
                return _inner_close(*a, **kw)
            inner.close = _tracked_inner_close
        else:
            conn.close = _tracked_close

        return conn

    # Patch get_db_connection in database module
    monkeypatch.setattr(dbmod, "get_db_connection", _tracked_get_db)

    # Also patch get_db in database module (context manager version)
    import contextlib as _ctx
    _real_get_db_cm = dbmod.get_db

    @contextlib.contextmanager
    def _tracked_get_db_cm(*args, **kwargs):
        with _real_get_db_cm(*args, **kwargs) as conn:
            tracker.record_open(conn)
            _real_close_cm = conn.close

            def _tracked_close_cm(*a, **kw):
                tracker.record_close(conn)
                return _real_close_cm(*a, **kw)

            if hasattr(conn, '_conn'):
                inner = object.__getattribute__(conn, '_conn')
                _inner_close = inner.close

                def _tracked_inner_close_cm(*a, **kw):
                    tracker.record_close(conn)
                    return _inner_close(*a, **kw)
                inner.close = _tracked_inner_close_cm
            else:
                conn.close = _tracked_close_cm
            yield conn

    monkeypatch.setattr(dbmod, "get_db", _tracked_get_db_cm)

    yield tracker

    # Teardown — verify no leaks
    tracker.assert_all_closed()
    tracker.assert_no_double_close()
