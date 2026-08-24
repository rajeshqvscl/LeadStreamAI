"""
Structured JSON Logging for Email Engine
Compatible with Loki, Datadog, CloudWatch, etc.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger


class EmailEngineJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with email engine fields"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['service'] = 'email-engine'
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                          'levelname', 'levelno', 'lineno', 'module', 'msecs', 
                          'message', 'name', 'pathname', 'process', 'processName',
                          'relativeCreated', 'thread', 'threadName', 'exc_info',
                          'exc_text', 'stack_info']:
                log_record[key] = value


def setup_structured_logging(level: int = logging.INFO):
    """Configure structured JSON logging for email engine"""
    handler = logging.StreamHandler(sys.stdout)
    formatter = EmailEngineJsonFormatter(
        fmt='%(timestamp)s %(level)s %(service)s %(logger)s %(message)s'
    )
    handler.setFormatter(formatter)
    
    # Configure email-engine logger
    engine_logger = logging.getLogger('email_engine')
    engine_logger.setLevel(level)
    engine_logger.handlers = [handler]
    engine_logger.propagate = False
    
    # Also configure app.email_engine logger
    app_logger = logging.getLogger('app.email_engine')
    app_logger.setLevel(level)
    app_logger.handlers = [handler]
    app_logger.propagate = False


def get_structured_logger(name: str) -> logging.Logger:
    """Get logger with structured logging configured"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        setup_structured_logging()
    return logger


class LogContext:
    """Context manager for adding consistent fields to logs"""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_extra = getattr(logger, '_email_engine_context', {})
    
    def __enter__(self):
        self.logger._email_engine_context = {**self.old_extra, **self.context}
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger._email_engine_context = self.old_extra


def log_with_context(logger: logging.Logger, level: int, message: str, **context):
    """Log with additional context fields"""
    extra = getattr(logger, '_email_engine_context', {})
    extra.update(context)
    logger.log(level, message, extra=extra)


# Convenience functions
def log_job_enqueued(logger: logging.Logger, job_id: str, user_id: int, priority: str, template: str):
    log_with_context(logger, logging.INFO, "Job enqueued",
        job_id=job_id, user_id=user_id, priority=priority, template=template,
        event="JOB_ENQUEUED")

def log_job_started(logger: logging.Logger, job_id: str, user_id: int):
    log_with_context(logger, logging.INFO, "Job started",
        job_id=job_id, user_id=user_id, event="JOB_STARTED")

def log_job_completed(logger: logging.Logger, job_id: str, user_id: int, 
                      thread_id: str, message_id: str, duration_ms: float):
    log_with_context(logger, logging.INFO, "Job completed",
        job_id=job_id, user_id=user_id, thread_id=thread_id, 
        message_id=message_id, duration_ms=duration_ms, event="JOB_COMPLETED")

def log_job_failed(logger: logging.Logger, job_id: str, user_id: int, 
                   error: str, retry_count: int, will_retry: bool):
    log_with_context(logger, logging.ERROR, "Job failed",
        job_id=job_id, user_id=user_id, error=error, 
        retry_count=retry_count, will_retry=will_retry, event="JOB_FAILED")

def log_rate_limited(logger: logging.Logger, user_id: int, wait_time: float):
    log_with_context(logger, logging.WARNING, "Rate limited",
        user_id=user_id, wait_time=wait_time, event="RATE_LIMITED")

def log_dlq(logger: logging.Logger, job_id: str, error: str):
    log_with_context(logger, logging.ERROR, "Job moved to DLQ",
        job_id=job_id, error=error, event="DLQ")