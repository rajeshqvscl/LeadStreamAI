"""
Unit tests for TokenBucket rate limiter.
Pure logic — no DB, no network.
Uses short sleeps for refill tests.
"""

import threading
import time

import pytest

from app.email_engine.worker.rate_limiter import TokenBucket


class TestTokenBucketConsume:
    """Test consume behavior with token availability."""

    def test_consume_succeeds_when_tokens_available(self):
        bucket = TokenBucket(rate=10, burst=10)
        assert bucket.consume(1) is True

    def test_consume_fails_when_tokens_depleted(self):
        bucket = TokenBucket(rate=1, burst=5)
        for _ in range(5):
            bucket.consume(1)
        assert bucket.consume(1) is False

    def test_consume_multiple_tokens(self):
        bucket = TokenBucket(rate=10, burst=10)
        assert bucket.consume(5) is True
        assert bucket.get_available() >= 4

    def test_consume_more_than_burst_fails(self):
        bucket = TokenBucket(rate=10, burst=5)
        assert bucket.consume(6) is False


class TestGetAvailable:
    """Test get_available returns current token count."""

    def test_initial_full_bucket(self):
        bucket = TokenBucket(rate=10, burst=10)
        available = bucket.get_available()
        assert available == 10

    def test_after_consume(self):
        bucket = TokenBucket(rate=10, burst=10)
        bucket.consume(3)
        available = bucket.get_available()
        assert available == pytest.approx(7, abs=0.5)

    def test_empty_bucket(self):
        bucket = TokenBucket(rate=1, burst=5)
        for _ in range(5):
            bucket.consume(1)
        available = bucket.get_available()
        assert available < 1


class TestRefill:
    """Test that tokens refill over time."""

    def test_refill_after_wait(self):
        bucket = TokenBucket(rate=100, burst=10)
        bucket.consume(10)
        assert bucket.get_available() < 1
        time.sleep(0.05)
        available = bucket.get_available()
        assert available > 0

    def test_refill_caps_at_burst(self):
        bucket = TokenBucket(rate=100, burst=10)
        # Consume nothing, wait, should still be capped at burst
        time.sleep(0.05)
        available = bucket.get_available()
        assert available <= 10

    def test_refill_after_partial_consume(self):
        bucket = TokenBucket(rate=100, burst=10)
        bucket.consume(5)
        time.sleep(0.1)
        available = bucket.get_available()
        assert available > 5


class TestBurstCapacity:
    """Test that burst amount can be consumed at once."""

    def test_burst_all_at_once(self):
        bucket = TokenBucket(rate=10, burst=10)
        assert bucket.consume(10) is True

    def test_burst_then_fail(self):
        bucket = TokenBucket(rate=10, burst=10)
        bucket.consume(10)
        assert bucket.consume(1) is False


class TestThreadSafety:
    """Concurrent consumes should not crash."""

    def test_concurrent_consumes(self):
        bucket = TokenBucket(rate=100, burst=50)
        results = []

        def consume_one():
            result = bucket.consume(1)
            results.append(result)

        threads = [threading.Thread(target=consume_one) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        assert sum(results) == 50
