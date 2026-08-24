"""
Atomic Claim Logic for Follow-up Sending
Prevents duplicate sends via atomic UPDATE ... WHERE stage = expected
"""

from typing import Optional, Tuple
from datetime import datetime
from app.database import get_db_connection
import logging

logger = logging.getLogger(__name__)


class LeadClaimer:
    """Handles atomic claim-before-send for follow-ups"""
    
    @staticmethod
    def claim_for_followup(
        lead_id: int,
        expected_stage: int,
        new_stage: int,
        subject: str,
        new_status: str = "ACTIVE"
    ) -> bool:
        """
        Atomically claim a lead for follow-up sending.
        Returns True if claim succeeded, False if already claimed by another worker.
        """
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE leads_raw
                SET followup_stage = %s,
                    followup_status = %s,
                    last_outreach_at = NOW(),
                    last_outreach_subject = %s,
                    email_status = 'SENT',
                    updated_at = NOW()
                WHERE id = %s 
                  AND followup_stage = %s 
                  AND followup_status = 'ACTIVE'
            """, (new_stage, new_status, subject, lead_id, expected_stage))
            conn.commit()
            claimed = cur.rowcount > 0
            if claimed:
                logger.info(f"Claimed lead {lead_id} for stage {new_stage}")
            else:
                logger.info(f"Lead {lead_id} stage {expected_stage} already claimed by another worker")
            return claimed
        except Exception as e:
            conn.rollback()
            logger.error(f"Claim failed for lead {lead_id}: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def rollback_claim(
        lead_id: int,
        old_stage: int,
        old_last_outreach_at: Optional[datetime],
        old_last_subject: Optional[str]
    ) -> bool:
        """
        Rollback a failed send - restore previous stage and timer.
        """
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE leads_raw
                SET followup_stage = %s,
                    followup_status = 'ACTIVE',
                    last_outreach_at = %s,
                    last_outreach_subject = %s,
                    updated_at = NOW()
                WHERE id = %s AND followup_stage = %s
            """, (old_stage, old_last_outreach_at, old_last_subject, lead_id, old_stage + 1))
            conn.commit()
            rolled_back = cur.rowcount > 0
            if rolled_back:
                logger.info(f"Rolled back lead {lead_id} to stage {old_stage}")
            return rolled_back
        except Exception as e:
            conn.rollback()
            logger.error(f"Rollback failed for lead {lead_id}: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def complete_sequence(lead_id: int) -> bool:
        """Mark follow-up sequence as completed"""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE leads_raw
                SET followup_status = 'COMPLETED',
                    updated_at = NOW()
                WHERE id = %s AND followup_status = 'ACTIVE'
            """, (lead_id,))
            conn.commit()
            completed = cur.rowcount > 0
            if completed:
                logger.info(f"Lead {lead_id} followup sequence completed")
            return completed
        except Exception as e:
            conn.rollback()
            logger.error(f"Complete sequence failed for lead {lead_id}: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def save_thread_ids(lead_id: int, thread_id: Optional[str], message_id: Optional[str]) -> bool:
        """Save Gmail thread/message IDs after successful send"""
        if not thread_id and not message_id:
            return True
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE leads_raw
                SET gmail_thread_id = COALESCE(%s, gmail_thread_id),
                    gmail_message_id = COALESCE(%s, gmail_message_id),
                    updated_at = NOW()
                WHERE id = %s
            """, (thread_id, message_id, lead_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save thread IDs for lead {lead_id}: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def log_activity(lead_id: int, action: str, details: str, performed_by: str = "system", user_id: Optional[int] = None):
        """Log activity for audit trail"""
        from app.models.lead import add_activity_log
        try:
            add_activity_log(lead_id, action, details, performed_by, user_id)
        except Exception as e:
            logger.warning(f"Activity log failed for lead {lead_id}: {e}")