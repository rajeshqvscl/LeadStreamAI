"""
Prometheus Metrics for LeadStreamAI.
Provides application-level metrics for monitoring and alerting.
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)

# Create custom registry to avoid conflicts
registry = CollectorRegistry()

# ============================================
# HTTP Request Metrics
# ============================================
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "endpoint"],
    registry=registry,
)

# ============================================
# Email Metrics
# ============================================
EMAILS_SENT_TOTAL = Counter(
    "emails_sent_total",
    "Total emails sent",
    ["user_id", "status", "template"],
    registry=registry,
)

EMAIL_SEND_DURATION = Histogram(
    "email_send_duration_seconds",
    "Email send latency in seconds",
    ["user_id", "template"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry,
)

EMAIL_QUEUE_SIZE = Gauge(
    "email_queue_size",
    "Number of emails in the send queue",
    ["user_id", "priority"],
    registry=registry,
)

EMAIL_DISPATCHER_ITERATIONS = Counter(
    "email_dispatcher_iterations_total",
    "Email dispatcher loop iterations",
    ["priority"],
    registry=registry,
)

EMAIL_DISPATCHER_POPS = Counter(
    "email_dispatcher_pops_total",
    "Jobs popped off the email queue by the dispatcher",
    ["priority", "outcome"],
    registry=registry,
)

EMAIL_DISPATCHER_ERRORS = Counter(
    "email_dispatcher_errors_total",
    "Email dispatcher loop errors",
    ["error"],
    registry=registry,
)

EMAIL_BOUNCES_TOTAL = Counter(
    "email_bounces_total",
    "Total email bounces",
    ["user_id", "bounce_type"],
    registry=registry,
)

EMAIL_OPENS_TOTAL = Counter(
    "email_opens_total",
    "Total email opens tracked",
    ["user_id", "template"],
    registry=registry,
)

EMAIL_CLICKS_TOTAL = Counter(
    "email_clicks_total",
    "Total email link clicks tracked",
    ["user_id", "template"],
    registry=registry,
)

EMAIL_UNSUBSCRIBES_TOTAL = Counter(
    "email_unsubscribes_total",
    "Total email unsubscribes",
    ["user_id", "source"],
    registry=registry,
)

# ============================================
# Lead Metrics
# ============================================
LEADS_TOTAL = Gauge(
    "leads_total",
    "Total leads in database",
    ["user_id", "status"],
    registry=registry,
)

LEADS_CREATED_TOTAL = Counter(
    "leads_created_total",
    "Total leads created",
    ["user_id", "source"],
    registry=registry,
)

LEADS_PIPELINE_STAGE = Gauge(
    "leads_pipeline_stage",
    "Number of leads in each pipeline stage",
    ["user_id", "stage"],
    registry=registry,
)

# ============================================
# Follow-up Metrics
# ============================================
FOLLOWUPS_SENT_TOTAL = Counter(
    "followups_sent_total",
    "Total follow-ups sent",
    ["user_id", "stage", "status"],
    registry=registry,
)

FOLLOWUPS_DUE = Gauge(
    "followups_due",
    "Number of follow-ups due to be sent",
    ["user_id", "stage"],
    registry=registry,
)

# ============================================
# Gmail API Metrics
# ============================================
GMAIL_API_CALLS_TOTAL = Counter(
    "gmail_api_calls_total",
    "Total Gmail API calls",
    ["user_id", "method", "status"],
    registry=registry,
)

GMAIL_API_DURATION = Histogram(
    "gmail_api_duration_seconds",
    "Gmail API call latency in seconds",
    ["user_id", "method"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

GMAIL_QUOTA_REMAINING = Gauge(
    "gmail_quota_remaining",
    "Remaining Gmail API quota",
    ["user_id"],
    registry=registry,
)

GMAIL_PUSH_NOTIFICATIONS_TOTAL = Counter(
    "gmail_push_notifications_total",
    "Total Gmail push notifications received",
    ["user_id", "status"],
    registry=registry,
)

# ============================================
# LLM Metrics
# ============================================
LLM_CALLS_TOTAL = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["provider", "model", "status"],
    registry=registry,
)

LLM_CALL_DURATION = Histogram(
    "llm_call_duration_seconds",
    "LLM API call latency in seconds",
    ["provider", "model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=registry,
)

LLM_TOKENS_USED = Counter(
    "llm_tokens_used_total",
    "Total LLM tokens used",
    ["provider", "model", "type"],  # type: prompt/completion
    registry=registry,
)

# ============================================
# RAG Metrics
# ============================================
RAG_PROCESSING_DURATION = Histogram(
    "rag_processing_duration_seconds",
    "RAG document processing latency",
    ["status"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=registry,
)

RAG_QUERIES_TOTAL = Counter(
    "rag_queries_total",
    "Total RAG queries",
    ["status"],
    registry=registry,
)

# ============================================
# Database Metrics
# ============================================
DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active",
    "Active database connections",
    registry=registry,
)

DB_CONNECTIONS_IDLE = Gauge(
    "db_connections_idle",
    "Idle database connections",
    registry=registry,
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query latency",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=registry,
)

DB_QUERIES_TOTAL = Counter(
    "db_queries_total",
    "Total database queries",
    ["query_type", "status"],
    registry=registry,
)

# ============================================
# Redis Metrics
# ============================================
REDIS_CONNECTIONS = Gauge(
    "redis_connections",
    "Active Redis connections",
    registry=registry,
)

REDIS_OPERATIONS_TOTAL = Counter(
    "redis_operations_total",
    "Total Redis operations",
    ["operation", "status"],
    registry=registry,
)

REDIS_OPERATION_DURATION = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation latency",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
    registry=registry,
)

# ============================================
# Scheduler Metrics
# ============================================
SCHEDULER_JOBS_RUN_TOTAL = Counter(
    "scheduler_jobs_run_total",
    "Total scheduler jobs executed",
    ["job_name", "status"],
    registry=registry,
)

SCHEDULER_JOB_DURATION = Histogram(
    "scheduler_job_duration_seconds",
    "Scheduler job execution time",
    ["job_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
    registry=registry,
)

SCHEDULER_LEADS_PROCESSED = Counter(
    "scheduler_leads_processed_total",
    "Total leads processed by scheduler",
    ["job_name", "status"],
    registry=registry,
)

# ============================================
# Business Metrics
# ============================================
REVENUE_PIPELINE = Gauge(
    "revenue_pipeline_total",
    "Total revenue in pipeline",
    ["user_id", "stage"],
    registry=registry,
)

MEETINGS_SCHEDULED_TOTAL = Counter(
    "meetings_scheduled_total",
    "Total meetings scheduled",
    ["user_id"],
    registry=registry,
)

REPLY_DETECTED_TOTAL = Counter(
    "reply_detected_total",
    "Total replies detected",
    ["user_id", "intent"],
    registry=registry,
)

# ============================================
# Helper Functions
# ============================================

def record_http_request(method: str, endpoint: str, status: int, duration: float):
    """Record HTTP request metrics."""
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


def record_email_sent(user_id: str, status: str, template: str, duration: float):
    """Record email sent metrics."""
    EMAILS_SENT_TOTAL.labels(user_id=user_id, status=status, template=template).inc()
    EMAIL_SEND_DURATION.labels(user_id=user_id, template=template).observe(duration)


def record_gmail_api_call(user_id: str, method: str, status: str, duration: float):
    """Record Gmail API call metrics."""
    GMAIL_API_CALLS_TOTAL.labels(user_id=user_id, method=method, status=status).inc()
    GMAIL_API_DURATION.labels(user_id=user_id, method=method).observe(duration)


def record_llm_call(provider: str, model: str, status: str, duration: float, prompt_tokens: int = 0, completion_tokens: int = 0):
    """Record LLM call metrics."""
    LLM_CALLS_TOTAL.labels(provider=provider, model=model, status=status).inc()
    LLM_CALL_DURATION.labels(provider=provider, model=model).observe(duration)
    if prompt_tokens:
        LLM_TOKENS_USED.labels(provider=provider, model=model, type="prompt").inc(prompt_tokens)
    if completion_tokens:
        LLM_TOKENS_USED.labels(provider=provider, model=model, type="completion").inc(completion_tokens)


def record_rag_processing(status: str, duration: float):
    """Record RAG processing metrics."""
    RAG_PROCESSING_DURATION.labels(status=status).observe(duration)
    RAG_QUERIES_TOTAL.labels(status=status).inc()


def record_db_query(query_type: str, status: str, duration: float):
    """Record database query metrics."""
    DB_QUERIES_TOTAL.labels(query_type=query_type, status=status).inc()
    DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)


def record_redis_operation(operation: str, status: str, duration: float):
    """Record Redis operation metrics."""
    REDIS_OPERATIONS_TOTAL.labels(operation=operation, status=status).inc()
    REDIS_OPERATION_DURATION.labels(operation=operation).observe(duration)


def record_scheduler_job(job_name: str, status: str, duration: float, leads_processed: int = 0):
    """Record scheduler job metrics."""
    SCHEDULER_JOBS_RUN_TOTAL.labels(job_name=job_name, status=status).inc()
    SCHEDULER_JOB_DURATION.labels(job_name=job_name).observe(duration)
    if leads_processed:
        SCHEDULER_LEADS_PROCESSED.labels(job_name=job_name, status=status).inc(leads_processed)


def record_reply_detected(user_id: str, intent: str):
    """Record reply detection metrics."""
    REPLY_DETECTED_TOTAL.labels(user_id=user_id, intent=intent).inc()


def record_meeting_scheduled(user_id: str):
    """Record meeting scheduled metrics."""
    MEETINGS_SCHEDULED_TOTAL.labels(user_id=user_id).inc()


# ============================================
# Middleware for automatic HTTP metrics
# ============================================

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically collect HTTP metrics."""
    
    async def dispatch(self, request: Request, call_next):
        method = request.method
        # Normalize endpoint for metrics (replace path params)
        path = request.url.path
        # Simple normalization - replace numeric IDs with placeholder
        import re
        normalized_path = re.sub(r'/\d+', '/:id', path)
        normalized_path = re.sub(r'/[a-f0-9-]{36}', '/:uuid', normalized_path)
        
        start_time = time.time()
        
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=normalized_path).inc()
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            record_http_request(method, normalized_path, response.status_code, duration)
            
            return response
        except Exception as e:
            duration = time.time() - start_time
            record_http_request(method, normalized_path, 500, duration)
            raise
        finally:
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=normalized_path).dec()


# ============================================
# Metrics Endpoint
# ============================================

async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )


# Import Response at module level
from fastapi import Response