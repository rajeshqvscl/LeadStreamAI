"""
Metrics Collection - Prometheus + Structured Logging
"""

import time
import logging
from typing import Optional
from functools import wraps
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from app.core.config import get_email_engine_settings

logger = logging.getLogger(__name__)

# Custom registry to avoid conflicts
registry = CollectorRegistry()

# Prometheus Metrics
jobs_enqueued = Counter(
    'email_engine_jobs_enqueued_total',
    'Total jobs enqueued',
    ['priority', 'user_id'],
    registry=registry
)

jobs_completed = Counter(
    'email_engine_jobs_completed_total',
    'Total jobs completed',
    ['status', 'template'],
    registry=registry
)

jobs_failed = Counter(
    'email_engine_jobs_failed_total',
    'Total jobs failed',
    ['error_type', 'template'],
    registry=registry
)

send_duration = Histogram(
    'email_engine_send_duration_seconds',
    'Email send duration in seconds',
    ['template'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

queue_depth = Gauge(
    'email_engine_queue_depth',
    'Current queue depth',
    ['priority'],
    registry=registry
)

rate_limit_remaining = Gauge(
    'email_engine_rate_limit_remaining',
    'Remaining rate limit tokens',
    ['user_id'],
    registry=registry
)

active_workers = Gauge(
    'email_engine_active_workers',
    'Number of active workers',
    ['user_id'],
    registry=registry
)


class MetricsCollector:
    """Collects and exports metrics"""
    
    @staticmethod
    def record_enqueue(priority: str, user_id: int):
        jobs_enqueued.labels(priority=priority, user_id=str(user_id)).inc()
    
    @staticmethod
    def record_completion(status: str, template: str):
        jobs_completed.labels(status=status, template=template).inc()
    
    @staticmethod
    def record_failure(error_type: str, template: str):
        jobs_failed.labels(error_type=error_type, template=template).inc()
    
    @staticmethod
    def record_duration(template: str, duration: float):
        send_duration.labels(template=template).observe(duration)
    
    @staticmethod
    def update_queue_depth(priority: str, depth: int):
        queue_depth.labels(priority=priority).set(depth)
    
    @staticmethod
    def update_rate_limit(user_id: int, remaining: int):
        rate_limit_remaining.labels(user_id=str(user_id)).set(remaining)
    
    @staticmethod
    def update_workers(user_id: int, count: int):
        active_workers.labels(user_id=str(user_id)).set(count)
    
    @staticmethod
    def export() -> bytes:
        """Export Prometheus metrics"""
        return generate_latest(registry)


def timed_operation(metric_name: str, template: str = "unknown"):
    """Decorator to time operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                MetricsCollector.record_completion("success", template)
                return result
            except Exception as e:
                MetricsCollector.record_failure(type(e).__name__, template)
                raise
            finally:
                duration = time.time() - start
                MetricsCollector.record_duration(template, duration)
        return wrapper
    return decorator