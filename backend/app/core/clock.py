"""
Authoritative Time Source (DB clock preferred over the machine clock)

Every scheduler decision that depends on the wall clock — fixed IST slots
(reply polling, cleanup, maintenance), working-hours windows, weekend skips —
must follow the DATABASE clock. A machine with a skewed system clock (e.g. a
dev laptop ~11h ahead) would otherwise fire emails, polls and maintenance at
the wrong IST time while the DB clock stays correct.

    from app.core.clock import now_ist

    now = now_ist()          # tz-aware datetime in IST, DB-sourced
    weekday = now.weekday()  # 0=Mon … 6=Sun

DB time is read with ``SELECT NOW()`` and cached briefly so the 2-second
scheduler loop does not hammer the connection pool. If the DB is unreachable
the local machine clock is used as a fallback (and a warning is logged once
per outage).
"""

import logging
import threading
import time as _time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

_CACHE_TTL_SECONDS = 15
# After a failed DB clock read, back off this long before trying again so a
# DB outage (or a DB-less test run) doesn't hammer the pool every call.
_FAILURE_BACKOFF_SECONDS = 30
_cache: dict = {}
_lock = threading.Lock()

# Epoch sanity floor: anything before 2017-07-14 is a stubbed/fake value.
_EPOCH_SANITY_FLOOR = 1_500_000_000


def now_ist() -> datetime:
    """Return the current time as a tz-aware IST datetime.

    Sources the DB clock when reachable; falls back to the local machine clock.
    """
    db_epoch = _db_now_epoch()
    if db_epoch is not None:
        return datetime.fromtimestamp(db_epoch, tz=timezone.utc).astimezone(IST)
    return datetime.now(IST)


def now_ist_naive() -> datetime:
    """Same as :func:`now_ist` but tz-naive — the format used by follow-up
    interval math and ``scheduled_at`` columns (naive IST)."""
    return now_ist().replace(tzinfo=None)


def _db_now_epoch() -> float | None:
    """UTC epoch seconds from ``SELECT NOW()``, cached for _CACHE_TTL_SECONDS.

    Returns None (and warns) when the DB is unreachable or returns nonsense,
    so callers fall back to the local clock.
    """
    global _cache
    now = _time.time()
    with _lock:
        cached = _cache.get("ts")
        if cached is not None and now - _cache.get("at", 0) < _CACHE_TTL_SECONDS:
            return cached
        # Back off after a failed read so we don't retry DB on every call
        last_fail = _cache.get("failed_at")
        if last_fail is not None and now - last_fail < _FAILURE_BACKOFF_SECONDS:
            return None

    try:
        from app.database import get_db_connection

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute("SELECT EXTRACT(EPOCH FROM NOW())")
                row = cur.fetchone()
                ts = float(row[0]) if row is not None else 0.0
            finally:
                cur.close()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"DB clock unavailable ({e}) — falling back to local clock")
        with _lock:
            _cache = {"failed_at": now}
        return None

    if ts < _EPOCH_SANITY_FLOOR:
        logger.warning("DB clock returned an implausible value — using local clock")
        with _lock:
            _cache = {"failed_at": now}
        return None

    with _lock:
        _cache = {"ts": ts, "at": now}
    return ts
