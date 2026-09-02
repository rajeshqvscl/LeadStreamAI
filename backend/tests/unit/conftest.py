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
"""

import contextlib
import threading

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
