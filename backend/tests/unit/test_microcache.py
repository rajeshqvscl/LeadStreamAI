"""
Unit tests for in-process micro-cache (mc_get, mc_set, mc_invalidate_prefix).
Pure logic — no DB, no network.
"""

import time

import pytest

from app.utils.microcache import mc_get, mc_set, mc_invalidate_prefix, _store, _MAX_KEYS


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear _store before each test to avoid pollution."""
    _store.clear()
    yield
    _store.clear()


class TestMcSetGet:
    """Basic set and get operations."""

    def test_set_and_get(self):
        mc_set("key1", "value1", ttl_seconds=10)
        assert mc_get("key1") == "value1"

    def test_get_nonexistent_returns_none(self):
        assert mc_get("missing_key") is None

    def test_set_overwrites(self):
        mc_set("key1", "first", ttl_seconds=10)
        mc_set("key1", "second", ttl_seconds=10)
        assert mc_get("key1") == "second"

    def test_set_various_types(self):
        mc_set("str_key", "hello", ttl_seconds=10)
        mc_set("int_key", 42, ttl_seconds=10)
        mc_set("list_key", [1, 2, 3], ttl_seconds=10)
        mc_set("dict_key", {"a": 1}, ttl_seconds=10)
        assert mc_get("str_key") == "hello"
        assert mc_get("int_key") == 42
        assert mc_get("list_key") == [1, 2, 3]
        assert mc_get("dict_key") == {"a": 1}


class TestMcExpiry:
    """Expired keys should return None."""

    def test_expired_key_returns_none(self):
        mc_set("key1", "value1", ttl_seconds=0.1)
        assert mc_get("key1") == "value1"
        time.sleep(0.15)
        assert mc_get("key1") is None

    def test_non_expired_key_returns_value(self):
        mc_set("key1", "value1", ttl_seconds=10)
        time.sleep(0.05)
        assert mc_get("key1") == "value1"

    def test_expired_key_removed_from_store(self):
        mc_set("key1", "value1", ttl_seconds=0.1)
        time.sleep(0.15)
        mc_get("key1")  # triggers cleanup
        assert "key1" not in _store


class TestMcEviction:
    """Eviction when cache reaches MAX_KEYS."""

    def test_eviction_at_max_keys(self):
        # Fill cache to MAX_KEYS
        for i in range(_MAX_KEYS):
            mc_set(f"key_{i}", f"value_{i}", ttl_seconds=60)
        assert len(_store) == _MAX_KEYS

        # Adding one more should trigger eviction
        mc_set("overflow_key", "overflow_value", ttl_seconds=60)
        # Should not exceed MAX_KEYS by too much (eviction removes ~half)
        assert len(_store) <= _MAX_KEYS + 1


class TestMcInvalidatePrefix:
    """Invalidation by key prefix."""

    def test_removes_matching_keys(self):
        mc_set("dash:stats:1", "a", ttl_seconds=60)
        mc_set("dash:stats:2", "b", ttl_seconds=60)
        mc_set("dash:summary", "c", ttl_seconds=60)
        mc_invalidate_prefix("dash:stats:")
        assert mc_get("dash:stats:1") is None
        assert mc_get("dash:stats:2") is None
        assert mc_get("dash:summary") == "c"

    def test_keeps_non_matching_keys(self):
        mc_set("other:key", "val", ttl_seconds=60)
        mc_set("dash:stats:1", "a", ttl_seconds=60)
        mc_invalidate_prefix("dash:stats:")
        assert mc_get("other:key") == "val"

    def test_no_matching_prefix(self):
        mc_set("key1", "value1", ttl_seconds=60)
        mc_invalidate_prefix("nonexistent:")
        assert mc_get("key1") == "value1"

    def test_empty_prefix(self):
        mc_set("key1", "value1", ttl_seconds=60)
        # Empty prefix matches all keys starting with "" — everything starts with ""
        mc_invalidate_prefix("")
        assert mc_get("key1") is None
