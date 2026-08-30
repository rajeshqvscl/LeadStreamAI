"""
Rate Limiter - Token Bucket per User
Enforces Gmail API quota: 100 requests/sec per user
"""

import logging
import threading
import time

from app.core.config import get_email_engine_settings

logger = logging.getLogger(__name__)


class TokenBucket:
    """Thread-safe token bucket for rate limiting"""

    def __init__(self, rate: int, burst: int):
        self.rate = rate          # tokens per second
        self.burst = burst        # max bucket size
        self.tokens = burst       # current tokens
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens, return True if successful"""
        with self.lock:
            now = time.monotonic()
            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_for_tokens(self, tokens: int = 1, max_wait: float = 30.0) -> bool:
        """Block until tokens available or max_wait exceeded"""
        start = time.monotonic()
        while time.monotonic() - start < max_wait:
            if self.consume(tokens):
                return True
            time.sleep(0.01)  # 10ms polling
        return False

    def get_available(self) -> float:
        """Get current available tokens"""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            return min(self.burst, self.tokens + elapsed * self.rate)


class RateLimiter:
    """Per-user rate limiter using token buckets"""

    def __init__(self):
        settings = get_email_engine_settings()
        self.rate = settings.gmail_rate_limit_per_sec
        self.burst = settings.gmail_burst_limit
        self.buckets: dict[int, TokenBucket] = {}
        self.lock = threading.Lock()

    def _get_bucket(self, user_id: int) -> TokenBucket:
        """Get or create token bucket for user"""
        with self.lock:
            if user_id not in self.buckets:
                self.buckets[user_id] = TokenBucket(self.rate, self.burst)
            return self.buckets[user_id]

    def acquire(self, user_id: int, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Acquire permission to send email for user.
        Blocks until token available or timeout.
        """
        bucket = self._get_bucket(user_id)
        return bucket.wait_for_tokens(tokens, timeout)

    def try_acquire(self, user_id: int, tokens: int = 1) -> bool:
        """Try to acquire without blocking"""
        bucket = self._get_bucket(user_id)
        return bucket.consume(tokens)

    def get_remaining(self, user_id: int) -> int:
        """Get approximate remaining tokens for user"""
        bucket = self._get_bucket(user_id)
        return int(bucket.get_available())

    def reset_user(self, user_id: int):
        """Reset user's bucket (e.g., after quota error)"""
        with self.lock:
            if user_id in self.buckets:
                del self.buckets[user_id]


# Singleton
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
