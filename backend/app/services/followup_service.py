import logging
from datetime import datetime, timedelta
from typing import List, Optional
import json
import psycopg2.extras

from app.database import get_db_connection
from app.services.email_service import send_email
from app.api.drafts import get_sender_profile, inject_signature
from app.services.llm_services import LLMService
from app.models.lead import add_activity_log

logger = logging.getLogger(__name__)

def generate_followup_preview(lead_id: int, user_id: int):
    """Generates a preview of the next follow-up email for the dashboard."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (lead_id, user_id))
        lead = cur.fetchone()
        if not lead:
            return {"error": "Lead not found"}

        current_stage = lead['followup_stage'] or 0
        next_stage = current_stage + 1
        
        if next_stage > 3:
            return {"error": "Sequence already completed"}

        llm = LLMService()
        lead_name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "there"
        original_content = lead.get('email_draft') or "our previous outreach"
        
        ai_body = llm.generate_followup(lead_name, original_content, next_stage)
        
        # Clean subject
        subject = "Following up"
        if "Subject: " in original_content:
            subject = "Re: " + original_content.split("\n\n")[0].replace("Subject: ", "").strip()

        # Inject Signature
        profile = get_sender_profile(str(user_id))
        full_body = inject_signature(ai_body, profile, lead_id)
        
        return {
            "lead_id": lead_id,
            "next_stage": next_stage,
            "subject": subject,
            "body": ai_body,
            "full_html": full_body.replace("\n", "<br>")
        }
    finally:
        cur.close()
        conn.close()

def process_outreach_sequences():
    """
    Background worker function that finds leads due for follow-ups 
    (Day 2, Day 5, and Day 10) and sends automated emails.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Find leads in 'ACTIVE' status, not responded
        cur.execute("""
            SELECT l.*, u.id as sender_id, u.email as sender_email, u.full_name as sender_name
            FROM leads_raw l
            JOIN users u ON l.user_id = u.id
            WHERE l.followup_status = 'ACTIVE' 
            AND l.is_responded = FALSE
            AND l.last_outreach_at <= NOW() - INTERVAL '2 days'
            ORDER BY l.last_outreach_at ASC
        """)
        
        leads_due = cur.fetchall()
        if not leads_due:
            cur.close()
            conn.close()
            return

        logger.info(f"Background Scan: {len(leads_due)} leads due across multiple users.")
        llm = LLMService()
        
        for lead in leads_due:
            lead_id = lead['id']
            stage = lead['followup_stage'] or 0
            last_sent = lead['last_outreach_at']
            now = datetime.now()
            
            days_since_last = (now - last_sent).days
            
            should_send = False
            next_stage = stage + 1
            
            if stage == 0 and days_since_last >= 2:
                should_send = True
            elif stage == 1 and days_since_last >= 3:
                should_send = True
            elif stage == 2 and days_since_last >= 5:
                should_send = True
                
            if not should_send or stage >= 3:
                continue

            # NOTE: In Manual Approval mode, we don't AUTO-SEND. 
            # We just log it so it shows up in the Dashboard.
            logger.info(f"Lead {lead_id} ({lead['email']}) is due for Stage {next_stage} follow-up. Waiting for manual approval.")
            
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in process_outreach_sequences: {e}")
