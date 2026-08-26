"""
In-process micro-cache for hot read endpoints.
Sits IN FRONT of Redis: same-process hits cost ~0ms (no network round-trip,
no JSON re-parse). Falls through to whatever the caller does on miss.
Values are stored as Python objects — nothing serializes until needed.
"""

import time

_store = {}
_MAX_KEYS = 300


def mc_get(key):
    item = _store.get(key)
    if item is None:
        return None
    expires_at, value = item
    if time.time() > expires_at:
        _store.pop(key, None)
        return None
    return value


def mc_set(key, value, ttl_seconds):
    if len(_store) >= _MAX_KEYS:
        # Drop roughly half the entries (oldest-inserted) to stay bounded
        now = time.time()
        for k in list(_store.keys())[: _MAX_KEYS // 2]:
            expired = _store.get(k)
            if expired is None or expired[0] <= now:
                _store.pop(k, None)
        if len(_store) >= _MAX_KEYS:
            for k in list(_store.keys())[: _MAX_KEYS // 2]:
                _store.pop(k, None)
    _store[key] = (time.time() + ttl_seconds, value)


def mc_invalidate_prefix(prefix):
    """Drop every cached key starting with `prefix` (e.g. 'dash-stats:', 'ctabs:')."""
    for k in [k for k in _store if k.startswith(prefix)]:
        _store.pop(k, None)
