"""
Unit tests for RetryPolicy (exponential backoff, retry decisions).
Pure logic — no DB, no network.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.email_engine.worker.retry import RetryPolicy
from app.email_engine.queue.job import EmailJob


def _make_policy(max_retries=3, base_delay=1.0, max_delay=30.0):
    """Build a RetryPolicy with known settings, bypassing __init__ lru_cache."""
    policy = object.__new__(RetryPolicy)
    policy.max_retries = max_retries
    policy.base_delay = base_delay
    policy.max_delay = max_delay
    policy.multiplier = 2.0
    return policy


def _make_job(retry_count=0):
    job = EmailJob(
        to_email="test@example.com",
        subject="Test",
        html_content="<p>Hi</p>",
        user_id=1,
    )
    job.retry_count = retry_count
    return job


class TestGetDelay:
    """Exponential backoff calculation."""

    def test_attempt_0(self):
        policy = _make_policy(base_delay=1.0, max_delay=30.0)
        assert policy.get_delay(0) == 1.0

    def test_attempt_1(self):
        policy = _make_policy(base_delay=1.0, max_delay=30.0)
        assert policy.get_delay(1) == 2.0

    def test_attempt_2(self):
        policy = _make_policy(base_delay=1.0, max_delay=30.0)
        assert policy.get_delay(2) == 4.0

    def test_attempt_3(self):
        policy = _make_policy(base_delay=1.0, max_delay=30.0)
        assert policy.get_delay(3) == 8.0

    def test_capped_at_max_delay(self):
        policy = _make_policy(base_delay=1.0, max_delay=5.0)
        # attempt 3 = 8.0, capped to 5.0
        assert policy.get_delay(3) == 5.0

    def test_capped_at_max_delay_high_attempt(self):
        policy = _make_policy(base_delay=1.0, max_delay=10.0)
        assert policy.get_delay(10) == 10.0

    def test_base_delay_scaling(self):
        policy = _make_policy(base_delay=2.0, max_delay=100.0)
        assert policy.get_delay(0) == 2.0
        assert policy.get_delay(1) == 4.0
        assert policy.get_delay(2) == 8.0


class TestShouldRetry:
    """Retry decisions based on retry count and error type."""

    def test_retry_when_under_max(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=1)
        assert policy.should_retry(job, Exception("something")) is True

    def test_no_retry_at_max_retries(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=3)
        assert policy.should_retry(job, Exception("something")) is False

    def test_no_retry_over_max(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=5)
        assert policy.should_retry(job, Exception("something")) is False

    def test_no_retry_unauthorized(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("unauthorized access")) is False

    def test_no_retry_permission_denied(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("permission denied")) is False

    def test_no_retry_not_found(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("resource not found")) is False

    def test_no_retry_invalid(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("invalid request format")) is False

    def test_no_retry_quota_exceeded(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("quota exceeded")) is False

    def test_retry_connection_reset(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("connection reset by peer")) is True

    def test_retry_timeout(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("request timeout")) is True

    def test_retry_generic_error(self):
        policy = _make_policy(max_retries=3)
        job = _make_job(retry_count=0)
        assert policy.should_retry(job, Exception("500 internal server error")) is True
