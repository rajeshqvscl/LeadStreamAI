"""
Failure Injection Tests

Tests that the system handles various failure modes gracefully:
- Gmail API failures (401, 429, timeout)
- Redis unavailable
- PostgreSQL unavailable
- LLM failures (timeout, malformed JSON)
- Duplicate webhooks
- Duplicate queue jobs
- Worker crash recovery
"""

import os
import socket
from urllib.parse import urlparse

import pytest
from unittest.mock import patch, MagicMock


def _db_reachable() -> bool:
    """True if a real PostgreSQL is listening on the configured DATABASE_URL.
    Raw TCP check so it is not fooled by app-level DB stubs."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return False
    p = urlparse(url.replace("postgresql://", "http://"))
    host = p.hostname or "localhost"
    port = p.port or 5432
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except Exception:
        return False


class TestGmailAPIFailures:
    """Test Gmail API failure handling."""

    def test_gmail_401_invalidates_cache(self):
        """Gmail 401 should invalidate cached service and clean tokens."""
        from app.services.google_service import invalidate_gmail_service_cache

        # Should not crash
        invalidate_gmail_service_cache(999)

    def test_gmail_send_with_no_service(self):
        """Send email when Gmail service is unavailable should fail gracefully."""
        from app.services.email_service import send_email

        with patch('app.services.google_service.get_gmail_service', return_value=None):
            success, msg, thread_id, msg_id = send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
                user_id=999,  # Non-existent user
            )
            assert success is False

    def test_retry_policy_non_retryable_errors(self):
        """Non-retryable errors should not be retried."""
        from app.email_engine.worker.retry import RetryPolicy

        policy = RetryPolicy()
        job = MagicMock()
        job.retry_count = 0

        # "unauthorized" is non-retryable
        error = Exception("unauthorized access")
        assert not policy.should_retry(job, error)

    def test_retry_policy_retryable_errors(self):
        """Retryable errors should be retried."""
        from app.email_engine.worker.retry import RetryPolicy

        policy = RetryPolicy()
        job = MagicMock()
        job.retry_count = 0

        # "rate limit" is retryable
        error = Exception("rate limit exceeded")
        assert policy.should_retry(job, error)

    def test_retry_policy_max_retries_exceeded(self):
        """After max retries, job should not be retried."""
        from app.email_engine.worker.retry import RetryPolicy

        policy = RetryPolicy()
        job = MagicMock()
        job.retry_count = policy.max_retries

        error = Exception("temporary error")
        assert not policy.should_retry(job, error)


class TestRedisFailures:
    """Test Redis unavailability handling."""

    def test_cache_miss_on_redis_down(self):
        """When Redis is down, should fall back to direct DB queries."""
        # This is tested implicitly by the leads.py cache logic
        # which gracefully falls back when redis_available is False
        pass

    def test_scheduler_lock_redis_down(self):
        """Scheduler lock should fail open when Redis is unavailable."""
        from app.core.scheduler_lock import SchedulerLock

        lock = SchedulerLock("test:lock", ttl_seconds=10)
        lock._redis = None  # Simulate no Redis

        # Should always acquire (fail open)
        assert lock.acquire() is True

    def test_rate_limiter_redis_down(self):
        """Rate limiter should not crash when Redis is unavailable."""
        # Rate limiter uses in-memory token buckets, not Redis
        from app.email_engine.worker.rate_limiter import RateLimiter

        limiter = RateLimiter()
        # Should work with in-memory buckets
        assert limiter.try_acquire(999) is True


class TestLLMFailures:
    """Test LLM failure handling."""

    def test_reply_classifier_llm_failure_fallback(self):
        """Reply classifier should fall back when all LLMs fail."""
        from app.core.reply.classifier import ReplyClassifier

        classifier = ReplyClassifier(llm_client=None)
        result = classifier.classify("Test reply")

        # Should return fallback result
        assert result.source == "FALLBACK"
        assert result.intent is None

    def test_reply_classifier_deterministic_override(self):
        """Decline phrases should work without any LLM."""
        from app.core.reply.classifier import ReplyClassifier

        classifier = ReplyClassifier(llm_client=None)
        result = classifier.classify("We will pass on this opportunity")

        assert result.intent == "NOT_INTERESTED"
        assert result.source == "DECLINE_PHRASE"

    def test_validator_rejects_invalid_llm_output(self):
        """Validator should reject malformed LLM output."""
        from app.core.reply.classifier import ClassificationResult
        from app.core.reply.validator import validate_classification

        result = ClassificationResult(
            intent="INVALID_INTENT",
            source="LLM",
            sentiment_score=50,
            urgency_level="MEDIUM",
            confidence=0.8,
        )

        validation = validate_classification(result)
        assert not validation.is_valid


class TestIdempotencyProtection:
    """Test idempotency protection under various scenarios."""

    def test_duplicate_job_same_key(self):
        """Same idempotency key should be claimed only once."""
        if not _db_reachable():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")
        from app.email_engine.worker.sender import claim_idempotency
        import uuid

        key = f"test_{uuid.uuid4().hex[:8]}"
        assert claim_idempotency(key) is True
        assert claim_idempotency(key) is False

    def test_different_keys_independent(self):
        """Different idempotency keys should be independent."""
        if not _db_reachable():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")
        from app.email_engine.worker.sender import claim_idempotency
        import uuid

        key1 = f"test_{uuid.uuid4().hex[:8]}"
        key2 = f"test_{uuid.uuid4().hex[:8]}"
        assert claim_idempotency(key1) is True
        assert claim_idempotency(key2) is True


class TestTokenEncryption:
    """Test token encryption under various conditions."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted token should decrypt correctly when key is set."""
        import os
        from app.utils.token_encryption import encrypt_token, decrypt_token, _get_fernet

        # Set a test encryption key
        os.environ['TOKEN_ENCRYPTION_KEY'] = 'test-key-for-unit-tests-12345'
        # Clear lru_cache so it picks up the new key
        _get_fernet.cache_clear()

        try:
            token = "ya29.test_token_12345"
            encrypted = encrypt_token(token)
            assert encrypted != token
            assert encrypted.startswith("enc:v1:")
            assert decrypt_token(encrypted) == token
        finally:
            # Cleanup
            del os.environ['TOKEN_ENCRYPTION_KEY']
            _get_fernet.cache_clear()

    def test_double_encrypt_not_applied(self):
        """Already encrypted token should not be re-encrypted."""
        from app.utils.token_encryption import encrypt_token, is_encrypted

        token = "enc:v1:already_encrypted"
        assert is_encrypted(token)
        assert encrypt_token(token) == token

    def test_none_passthrough(self):
        """None values should pass through unchanged."""
        from app.utils.token_encryption import encrypt_token, decrypt_token

        assert encrypt_token(None) is None
        assert decrypt_token(None) is None

    def test_plaintext_fallback_without_key(self):
        """Without TOKEN_ENCRYPTION_KEY, falls back to plaintext."""
        import os
        from app.utils.token_encryption import encrypt_token, _get_fernet

        # Ensure no key is set, then restore it so later tests still encrypt
        had_key = os.environ.pop('TOKEN_ENCRYPTION_KEY', None)
        try:
            _get_fernet.cache_clear()

            token = "test_token"
            result = encrypt_token(token)
            assert result == token  # Falls back to plaintext
        finally:
            if had_key is not None:
                os.environ['TOKEN_ENCRYPTION_KEY'] = had_key
            _get_fernet.cache_clear()


class TestWorkerOwnershipValidation:
    """Test worker ownership validation under edge cases."""

    def test_worker_rejects_nonexistent_lead(self):
        """Worker should reject job for non-existent lead."""
        import os
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not set — skipping DB-dependent test")

        from app.email_engine.worker.sender import _validate_job_ownership
        from app.email_engine.queue.job import EmailJob

        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
            user_id=1,
            lead_id=999999,
        )

        is_valid, error = _validate_job_ownership(job)
        assert not is_valid
        assert "not found" in error.lower() or "validation failed" in error.lower()

    def test_worker_allows_no_lead_job(self):
        """System emails without lead_id should pass."""
        from app.email_engine.worker.sender import _validate_job_ownership
        from app.email_engine.queue.job import EmailJob

        job = EmailJob(
            to_email="admin@example.com",
            subject="System Alert",
            html_content="<p>Alert</p>",
            user_id=1,
            lead_id=None,
        )

        is_valid, error = _validate_job_ownership(job)
        assert is_valid


class TestConcurrentSafety:
    """Test concurrent access safety."""

    def test_concurrent_idempotency_claims(self):
        """Concurrent claims on same key should result in exactly one success."""
        if not _db_reachable():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")
        from app.email_engine.worker.sender import claim_idempotency
        import uuid
        import concurrent.futures

        key = f"test_concurrent_{uuid.uuid4().hex[:8]}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(claim_idempotency, key) for _ in range(10)]
            results = [f.result() for f in futures]

        # Exactly one should succeed
        assert sum(results) == 1
