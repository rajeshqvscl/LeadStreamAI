"""
Gmail Sender - Thin wrapper around existing send_email logic.
Called by worker to actually send emails.
"""

import logging
from typing import Optional, Tuple, Dict, Any
from app.services.email_service import send_email
from app.email_engine.queue.job import EmailJob
from app.email_engine.worker.retry import get_retry_policy

logger = logging.getLogger(__name__)


def _send_email_once(job: EmailJob) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """Single email send attempt - extracted for retry logic"""
    return send_email(
        to_email=job.to_email,
        subject=job.subject,
        html_content=job.html_content,
        from_email=job.from_email,
        from_name=job.from_name,
        attachments=job.attachments if job.attachments else None,
        lead_id=job.lead_id,
        is_system_email=False,
        user_id=job.user_id,
        cc=job.cc,
        thread_id=job.thread_id,
        in_reply_to=job.in_reply_to,
        template_name=job.template_name,
    )


def send_email_job(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker entry point - called by RQ worker.
    Returns dict with success status and metadata.
    Implements 3 automatic retries with exponential backoff.
    """
    job = EmailJob.from_dict(job_data)
    retry_policy = get_retry_policy()
    
    # Check idempotency
    if job.idempotency_key:
        if not check_idempotency(job.idempotency_key):
            return {
                "success": False,
                "error": "Duplicate send prevented by idempotency key",
                "duplicate": True,
            }
    
    try:
        # Execute with retry policy (3 retries with exponential backoff)
        success, message, thread_id, message_id = retry_policy.execute_with_retry(
            job,
            _send_email_once,
            job,
        )
        
        # Record idempotency key on success
        if success and job.idempotency_key:
            save_idempotency(job.idempotency_key)
        
        return {
            "success": success,
            "message": message,
            "thread_id": thread_id,
            "message_id": message_id,
            "job_id": job.idempotency_key,
            "retry_count": job.retry_count,
        }
        
    except Exception as e:
        logger.error(f"Send email job failed after {job.retry_count} retries: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "retry_count": job.retry_count,
        }


def check_idempotency(key: str) -> bool:
    """Check if idempotency key exists (not already sent)"""
    from app.database import get_db_connection
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM email_idempotency WHERE key = %s AND expires_at > NOW()", (key,))
        exists = cur.fetchone() is not None
        return not exists
    finally:
        cur.close()
        conn.close()


def save_idempotency(key: str, ttl_hours: int = 24):
    """Save idempotency key with expiration"""
    from datetime import datetime, timedelta
    from app.database import get_db_connection
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        cur.execute("""
            INSERT INTO email_idempotency (key, expires_at)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET expires_at = EXCLUDED.expires_at
        """, (key, expires_at))
        conn.commit()
    finally:
        cur.close()
        conn.close()


# For backward compatibility with existing code
def send_email_direct(
    to_email: str,
    subject: str,
    html_content: str,
    user_id: int,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    lead_id: Optional[int] = None,
    cc: Optional[str] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Direct synchronous send (bypasses queue).
    Used for testing and immediate sends.
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        from_email=from_email,
        from_name=from_name,
        lead_id=lead_id,
        is_system_email=False,
        user_id=user_id,
        cc=cc,
        thread_id=thread_id,
        in_reply_to=in_reply_to,
    )