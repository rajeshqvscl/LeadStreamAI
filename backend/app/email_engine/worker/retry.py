"""
Retry Policy - Exponential Backoff + Dead Letter Queue
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from app.core.config import get_email_engine_settings
from app.email_engine.queue.job import EmailJob
from app.email_engine.queue.registry import get_dead_letter_queue

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Configurable retry policy with exponential backoff"""

    def __init__(self):
        settings = get_email_engine_settings()
        self.max_retries = settings.max_retries
        self.base_delay = settings.retry_base_delay_sec
        self.max_delay = settings.retry_max_delay_sec
        self.multiplier = 2.0  # exponential factor

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)"""
        delay = self.base_delay * (self.multiplier ** attempt)
        return min(delay, self.max_delay)

    def should_retry(self, job: EmailJob, error: Exception) -> bool:
        """Determine if job should be retried"""
        if job.retry_count >= self.max_retries:
            return False

        # Don't retry certain error types
        error_str = str(error).lower()
        non_retryable = [
            "unauthorized",
            "permission denied",
            "not found",
            "invalid",
            "quota exceeded",
        ]

        for nr in non_retryable:
            if nr in error_str:
                logger.info(f"Non-retryable error for job {job.idempotency_key}: {nr}")
                return False

        return True

    def execute_with_retry(self, job: EmailJob, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            job.retry_count = attempt

            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for job {job.idempotency_key}: {e}")

                if attempt < self.max_retries and self.should_retry(job, e):
                    delay = self.get_delay(attempt)
                    logger.info(f"Retrying job {job.idempotency_key} in {delay}s (attempt {attempt + 2})")
                    time.sleep(delay)
                else:
                    break

        # All retries exhausted - move to dead letter queue
        self.move_to_dead_letter(job, last_error)
        raise last_error

    def move_to_dead_letter(self, job: EmailJob, error: Exception):
        """Move failed job to dead letter queue"""
        try:
            dlq = get_dead_letter_queue()
            job.last_error = str(error)

            dlq.enqueue(
                'app.email_engine.worker.sender.send_email_job',
                job.to_dict(),
                job_id=f"dlq_{job.idempotency_key}",
                meta={
                    'job_data': job.to_dict(),
                    'failure_reason': str(error),
                    'attempts': job.retry_count,
                },
            )
            logger.error(f"Moved job {job.idempotency_key} to dead letter queue after {job.retry_count} attempts")
        except Exception as e:
            logger.exception(f"Failed to move job to DLQ: {e}")


# Default retry policy instance
_default_policy: RetryPolicy | None = None


def get_retry_policy() -> RetryPolicy:
    global _default_policy
    if _default_policy is None:
        _default_policy = RetryPolicy()
    return _default_policy
