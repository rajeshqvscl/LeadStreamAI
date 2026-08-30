"""
Metrics Export and Collection
Re-exports worker metrics and adds email-engine specific metrics
"""

# Email engine specific metrics
from prometheus_client import CollectorRegistry, Counter, Histogram

from app.email_engine.worker.metrics import (
    MetricsCollector,
    jobs_completed,
    jobs_enqueued,
    jobs_failed,
    send_duration,
    timed_operation,
)

email_engine_registry = CollectorRegistry()

emails_sent_total = Counter(
    'email_engine_emails_sent_total',
    'Total emails sent via Gmail API',
    ['user_id', 'template', 'lead_type'],
    registry=email_engine_registry
)

emails_failed_total = Counter(
    'email_engine_emails_failed_total',
    'Total emails failed',
    ['user_id', 'error_type', 'template'],
    registry=email_engine_registry
)

gmail_api_latency = Histogram(
    'email_engine_gmail_api_latency_seconds',
    'Gmail API call latency',
    ['operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=email_engine_registry
)

thread_healing_count = Counter(
    'email_engine_thread_healing_total',
    'Thread healing attempts',
    ['result'],
    registry=email_engine_registry
)

unsubscribe_clicks = Counter(
    'email_engine_unsubscribe_clicks_total',
    'Unsubscribe link clicks',
    ['lead_id', 'user_id'],
    registry=email_engine_registry
)

email_opens = Counter(
    'email_engine_opens_total',
    'Email open tracking pixel hits',
    ['lead_id', 'user_id'],
    registry=email_engine_registry
)

email_clicks = Counter(
    'email_engine_clicks_total',
    'Email link click tracking hits',
    ['lead_id', 'user_id'],
    registry=email_engine_registry
)


def export_all_metrics() -> bytes:
    """Export both worker and email engine metrics"""
    from prometheus_client import generate_latest
    return generate_latest(email_engine_registry) + generate_latest()


__all__ = [
    "MetricsCollector",
    "timed_operation",
    "jobs_enqueued",
    "jobs_completed",
    "jobs_failed",
    "send_duration",
    "emails_sent_total",
    "emails_failed_total",
    "gmail_api_latency",
    "thread_healing_count",
    "unsubscribe_clicks",
    "email_opens",
    "email_clicks",
    "export_all_metrics",
]
