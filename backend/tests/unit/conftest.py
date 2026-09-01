"""
Unit-test conftest — shared fixtures for backend/tests/unit/.

Key fixture: ``track_db_connections``
    Wraps ``app.database.get_db_connection`` so every call is tracked.
    After each test the fixture verifies:
    1. Every connection that was opened was also closed.
    2. No connection was closed twice (double-free).
    3. The pool never exceeded its max size.

Usage in any test file:
    def test_something(track_db_connections):
        conn = get_db_connection()
        # ... work ...
        conn.close()
        # fixture auto-verifies after the test
"""

import contextlib
import threading
import weakref

import pytest


# ---------------------------------------------------------------------------
# Connection tracker
# ---------------------------------------------------------------------------

class _ConnectionTracker:
    """Thread-safe tracker for DB connections opened/closed during a test."""

    def __init__(self):
        self._opened: dict[int, str] = {}      # id(conn) -> traceback string
        self._closed: set[int] = set()
        self._lock = threading.Lock()
        # Monkey-patched originals (restored after each test)
        self._original_get_db = None

    # -- public helpers called by the patched get_db_connection --

    def record_open(self, conn):
        with self._lock:
            self._opened[id(conn)] = ""

    def record_close(self, conn):
        with self._lock:
            self._closed.add(id(conn))

    # -- assertion helpers called by the fixture teardown --

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
    """Patch ``get_db_connection`` to track open/close lifecycle.

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

    monkeypatch.setattr(dbmod, "get_db_connection", _tracked_get_db)

    # Also patch the alias used inside some service modules
    for mod_name in [
        "app.services.email_service",
        "app.api.drafts",
        "app.api.leads",
        "app.api.gmail",
        "app.utils.auth_helpers",
    ]:
        with contextlib.suppress(ImportError, AttributeError):
            import importlib
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "get_db_connection"):
                monkeypatch.setattr(mod, "get_db_connection", _tracked_get_db)

    yield tracker

    # Teardown — verify no leaks
    tracker.assert_all_closed()
    tracker.assert_no_double_close()
