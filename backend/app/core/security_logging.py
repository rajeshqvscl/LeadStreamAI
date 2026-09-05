"""
Security Event Logging & Sensitive Data Redaction

Provides:
1. Security event logger for cross-user attempts, auth failures, suspicious exports
2. Redaction filter for OAuth tokens, API keys, and credentials in logs
"""

import logging
import re
from functools import wraps

# Patterns for sensitive data that must never appear in logs
REDACTION_PATTERNS = [
    # OAuth tokens (long base64 strings)
    (re.compile(r'(google_access_token|google_refresh_token|access_token|refresh_token)\s*[=:]\s*["\']?([A-Za-z0-9_\-\.]{20,})["\']?', re.IGNORECASE), r'\1=REDACTED'),
    # Bearer tokens
    (re.compile(r'(Bearer\s+)([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE), r'\1REDACTED'),
    # API keys
    (re.compile(r'(api_key|apikey|api-key)\s*[=:]\s*["\']?([A-Za-z0-9_\-\.]{16,})["\']?', re.IGNORECASE), r'\1=REDACTED'),
    # Passwords
    (re.compile(r'(password|passwd|pwd)\s*[=:]\s*["\']?([^\s"\']{4,})["\']?', re.IGNORECASE), r'\1=REDACTED'),
    # Database URLs with credentials
    (re.compile(r'(postgresql://[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1REDACTED\3'),
    (re.compile(r'(redis://[^:]*:)([^@]+)(@)', re.IGNORECASE), r'\1REDACTED\3'),
    # Gmail tokens (long alphanumeric strings that look like OAuth)
    (re.compile(r'ya29\.[A-Za-z0-9_\-]+', re.IGNORECASE), 'ya29.REDACTED'),
    (re.compile(r'1//[A-Za-z0-9_\-]+', re.IGNORECASE), '1//REDACTED'),
]


def redact_sensitive(text: str) -> str:
    """Redact sensitive values from a string before logging."""
    if not text:
        return text
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    """Logging filter that automatically redacts sensitive data from log records."""

    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = redact_sensitive(record.msg)
        if record.args and isinstance(record.args, tuple):
            record.args = tuple(
                redact_sensitive(str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True


# --- Security Event Logger ---

_security_logger = None


def get_security_logger() -> logging.Logger:
    """Get or create the security event logger."""
    global _security_logger
    if _security_logger is None:
        _security_logger = logging.getLogger("security")
        _security_logger.setLevel(logging.INFO)
    return _security_logger


def log_security_event(
    event_type: str,
    user_id: str | None = None,
    details: str = "",
    ip_address: str | None = None,
    severity: str = "WARNING",
):
    """
    Log a security-relevant event.

    Event types:
    - CROSS_USER_ACCESS_ATTEMPT: User tried to access another user's resource
    - AUTH_FAILURE: Login or token verification failed
    - SUSPICIOUS_EXPORT: Unusually large data export
    - OWNERSHIP_MISMATCH: Worker found lead doesn't belong to job user
    - ORPHAN_REPLY: Reply couldn't be matched to any lead
    - TOKEN_INVALID: OAuth token invalid/revoked
    - PERMISSION_DENIED: Authorization check failed
    """
    logger = get_security_logger()
    log_method = getattr(logger, severity.lower(), logger.warning)

    extra_fields = {
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
    }

    log_method(
        f"SECURITY_EVENT: {event_type} | user={user_id} | ip={ip_address} | {details}",
        extra=extra_fields,
    )

    # Also log to activity_log for audit trail if possible
    try:
        from app.models.lead import add_activity_log
        if user_id and user_id.isdigit():
            add_activity_log(
                None,  # no specific lead
                f"SECURITY_{event_type}",
                details,
                "security",
                int(user_id),
            )
    except Exception:
        pass  # Never fail on audit logging


def setup_security_logging():
    """Configure security logging with redaction filter."""
    security_logger = get_security_logger()

    # Add redaction filter to all loggers
    redact_filter = RedactingFilter()
    logging.getLogger().addFilter(redact_filter)

    # Also add to common loggers that might handle sensitive data
    for logger_name in ["uvicorn.access", "uvicorn.error", "app", "app.services"]:
        logging.getLogger(logger_name).addFilter(redact_filter)

    security_logger.info("Security logging initialized with redaction filter")
