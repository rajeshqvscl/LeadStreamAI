"""
Structured Logging Configuration using structlog.
Provides JSON-formatted logs with consistent fields for observability.
"""
import sys
import structlog
import logging
from typing import Any, Dict


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    service_name: str = "leadstreamai-backend",
) -> None:
    """
    Configure structlog for structured logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON; if False, output human-readable
        service_name: Name of the service for log identification
    """
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Configure structlog processors
    processors = [
        # Merge request-scoped contextvars (request_id, user_id, ...) into every log
        structlog.contextvars.merge_contextvars,
        # Add log level and logger name
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        
        # Add service name via custom processor
        lambda logger, method_name, event_dict: {**event_dict, "service": service_name},
        
        # Handle positional arguments
        structlog.stdlib.PositionalArgumentsFormatter(),
        
        # Add stack trace info for exceptions
        structlog.processors.StackInfoRenderer(),
        
        # Format exception info
        structlog.processors.format_exc_info,
        
        # Decode bytes to string
        structlog.processors.UnicodeDecoder(),
        
        # Render as JSON or console
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer(),
    ]
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("groq").setLevel(logging.WARNING)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structlog logger instance."""
    return structlog.get_logger(name)


# Context managers for adding request context
class LoggingContext:
    """Context manager for adding request-scoped context to logs."""
    
    def __init__(self, **context: Any):
        self.context = context
        self.token = None
    
    def __enter__(self):
        self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self
    
    def __exit__(self, *args):
        structlog.contextvars.unbind_contextvars(*self.context.keys())
        if self.token:
            structlog.contextvars.reset_contextvars(self.token)


def bind_request_context(
    request_id: str = None,
    user_id: str = None,
    endpoint: str = None,
    method: str = None,
    **extra: Any,
) -> LoggingContext:
    """Bind request context to current logging context."""
    context = {}
    if request_id:
        context["request_id"] = request_id
    if user_id:
        context["user_id"] = user_id
    if endpoint:
        context["endpoint"] = endpoint
    if method:
        context["method"] = method
    context.update(extra)
    return LoggingContext(**context)


# Helper functions for common log patterns
def log_request_start(logger: structlog.BoundLogger, method: str, path: str, user_id: str = None, **extra):
    """Log incoming request."""
    logger.info(
        "request_started",
        method=method,
        path=path,
        user_id=user_id,
        **extra,
    )


def log_request_end(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    user_id: str = None,
    **extra,
):
    """Log completed request."""
    logger.info(
        "request_completed",
        method=method,
        path=path,
        status_code=status_code,
        latency_ms=latency_ms,
        user_id=user_id,
        **extra,
    )


def log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    context: Dict[str, Any] = None,
    **extra,
):
    """Log error with context."""
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context or {},
        **extra,
    )


def log_business_event(
    logger: structlog.BoundLogger,
    event: str,
    **data,
):
    """Log business event (e.g., email_sent, lead_created, reply_detected)."""
    logger.info(
        "business_event",
        event=event,
        **data,
    )


# Pre-configured loggers for common use cases
email_logger = get_logger("email")
lead_logger = get_logger("lead")
reply_logger = get_logger("reply")
scheduler_logger = get_logger("scheduler")
auth_logger = get_logger("auth")
db_logger = get_logger("database")
rag_logger = get_logger("rag")
gmail_logger = get_logger("gmail")