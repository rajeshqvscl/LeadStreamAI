"""
Gmail Sender - Thin wrapper around existing send_email logic.
Called by worker to actually send emails.
"""

import logging
from typing import Any

from app.email_engine.queue.job import EmailJob
from app.email_engine.worker.retry import get_retry_policy
from app.services.email_service import send_email

logger = logging.getLogger(__name__)


def _send_email_once(job: EmailJob) -> tuple[bool, str, str | None, str | None]:
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
        signature_id=job.signature_id,
    )


def _validate_job_ownership(job: 'EmailJob') -> tuple[bool, str]:
    """
    SECURITY: Validate that the job's lead belongs to the job's user.
    Worker must NEVER trust queue payload blindly — DB is source of truth.
    Returns (is_valid, error_message).
    """
    if not job.lead_id or not job.user_id:
        # System emails (no lead_id) or broadcast jobs pass through
        return True, ""

    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, user_id, email_status, followup_status, pipeline_state "
                "FROM leads_raw WHERE id = %s",
                (job.lead_id,),
            )
            lead = cur.fetchone()
            if not lead:
                return False, f"Lead {job.lead_id} not found in DB"

            lead_user_id = lead['user_id']

            # Ownership check: lead must belong to the job's user
            if lead_user_id is not None and str(lead_user_id) != str(job.user_id):
                logger.error(
                    f"SECURITY: Ownership mismatch — job user={job.user_id}, "
                    f"lead {job.lead_id} owner={lead_user_id}. Blocking send."
                )
                return False, (
                    f"Ownership mismatch: lead {job.lead_id} belongs to user "
                    f"{lead_user_id}, not {job.user_id}"
                )

            # State guard: don't send to leads in terminal/stop states
            terminal_states = {'CLOSED_WON', 'CLOSED_LOST', 'UNSUBSCRIBED', 'BOUNCED'}
            stop_statuses = {'REPLIED', 'CLOSED'}
            stop_followups = {'STOPPED', 'COMPLETED'}

            if (lead.get('pipeline_state') or '') in terminal_states:
                return False, f"Lead {job.lead_id} in terminal state {lead['pipeline_state']}"
            if (lead.get('email_status') or '') in stop_statuses:
                return False, f"Lead {job.lead_id} has status {lead['email_status']}"
            if (lead.get('followup_status') or '') in stop_followups:
                return False, f"Lead {job.lead_id} followup is {lead['followup_status']}"

            # Gmail account ownership: verify user has Google tokens
            cur.execute(
                "SELECT google_refresh_token FROM users WHERE id = %s",
                (job.user_id,),
            )
            user_row = cur.fetchone()
            if not user_row or not user_row[0]:
                return False, f"User {job.user_id} has no Gmail connection"

            return True, ""
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        logger.exception(f"Ownership validation error for job {job.idempotency_key}: {e}")
        # Fail closed — don't send if we can't verify ownership
        return False, f"Ownership validation failed: {e}"


def send_email_job(job_data: dict[str, Any]) -> dict[str, Any]:
    """
    Worker entry point - called by RQ worker.
    Returns dict with success status and metadata.
    Implements 3 automatic retries with exponential backoff.
    """
    job = EmailJob.from_dict(job_data)
    retry_policy = get_retry_policy()

    # SECURITY: Validate ownership before doing anything else
    is_valid, error_msg = _validate_job_ownership(job)
    if not is_valid:
        logger.warning(f"Job {job.idempotency_key} rejected: {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "ownership_rejected": True,
        }

    # SECURITY FIX: Atomic idempotency claim BEFORE sending.
    # Old flow: SELECT(check) → send → INSERT(mark) — race window between check and insert.
    # New flow: INSERT(claim) → send — only the first worker to INSERT succeeds.
    if job.idempotency_key:
        if not claim_idempotency(job.idempotency_key):
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

        # Idempotency key already claimed atomically before send — no need to save again.

        # BUG 3: persist Gmail thread/message ids and log activity for follow-ups.
        # Wrapped in try/except so logging failures never break the send result.
        if success and getattr(job, 'lead_id', None):
            try:
                from app.core.pipeline.claims import LeadClaimer
                LeadClaimer.save_thread_ids(job.lead_id, thread_id, message_id)
            except Exception as _e:
                logger.warning(f"Failed to save thread ids for lead {job.lead_id}: {_e}")
            try:
                if job.idempotency_key and str(job.idempotency_key).startswith("followup_lead"):
                    from app.core.pipeline.claims import LeadClaimer as _LC
                    _LC.log_activity(
                        job.lead_id,
                        'AUTO_FOLLOWUP_SENT',
                        'Follow-up sent',
                        user_id=getattr(job, 'user_id', None),
                    )
            except Exception as _e:
                logger.warning(f"Failed to log follow-up activity for lead {job.lead_id}: {_e}")

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


def claim_idempotency(key: str, ttl_hours: int = 24) -> bool:
    """
    SECURITY FIX: Atomic idempotency claim using INSERT ... ON CONFLICT.
    Only the first worker to successfully INSERT gets to send.
    All subsequent workers get False (already claimed).

    Returns True if this caller claimed the key (safe to send).
    Returns False if already claimed by another worker (skip send).
    """
    from datetime import datetime, timedelta

    from app.database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        cur.execute("""
            INSERT INTO email_idempotency (key, expires_at)
            VALUES (%s, %s)
            ON CONFLICT (key) DO NOTHING
        """, (key, expires_at))
        claimed = cur.rowcount > 0
        conn.commit()
        if not claimed:
            logger.info(f"Idempotency claim failed for {key} — already claimed by another worker")
        return claimed
    except Exception as e:
        conn.rollback()
        logger.exception(f"Idempotency claim error for {key}: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def check_idempotency(key: str) -> bool:
    """Check if idempotency key exists (not already sent). Legacy wrapper."""
    return claim_idempotency(key)


def save_idempotency(key: str, ttl_hours: int = 24):
    """Save idempotency key with expiration. Now a no-op since claim_idempotency handles it."""
    pass  # claim_idempotency() already inserted the key atomically


# For backward compatibility with existing code
def send_email_direct(
    to_email: str,
    subject: str,
    html_content: str,
    user_id: int,
    from_email: str | None = None,
    from_name: str | None = None,
    lead_id: int | None = None,
    cc: str | None = None,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    signature_id: int | None = None,
) -> tuple[bool, str, str | None, str | None]:
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
        signature_id=signature_id,
    )
