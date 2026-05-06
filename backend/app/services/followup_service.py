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
        original_content = lead.get('last_outreach_body') or lead.get('email_draft') or "our previous outreach"
        
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
    Background worker that identifies leads due for follow-ups.
    Client: Stage 1 (Day 2), Stage 2 (Day 4)
    Investor: Stage 1 (Day 7), Stage 2 (Day 17)
    
    Instead of auto-sending, it generates a draft and marks it for approval.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Find leads in 'ACTIVE' or 'STOPPED' (if we want to restart) status
        # strictly those that have not responded.
        cur.execute("""
            SELECT l.*, u.id as sender_id, u.email as sender_email, u.full_name as sender_name
            FROM leads_raw l
            JOIN users u ON l.user_id = u.id
            WHERE (l.followup_status = 'ACTIVE' OR l.followup_status IS NULL)
            AND l.email_status = 'SENT'
            AND COALESCE(l.is_responded, FALSE) = FALSE
            AND l.followup_stage < 2
            AND (l.followup_draft IS NULL OR l.followup_approved = TRUE)
            ORDER BY l.last_outreach_at ASC
        """)
        
        leads = cur.fetchall()
        if not leads:
            cur.close()
            conn.close()
            return

        llm = LLMService()
        
        for lead in leads:
            lead_id = lead['id']
            stage = lead['followup_stage'] or 0
            last_sent = lead['last_outreach_at']
            if not last_sent: continue
            
            # Determine Lead Type (Client vs Investor)
            is_investor = True
            lead_type_raw = str(lead.get('lead_type') or lead.get('sector') or lead.get('persona') or '').upper()
            if 'CLIENT' in lead_type_raw or 'CUSTOMER' in lead_type_raw:
                is_investor = False

            now = datetime.now()
            days_since_last = (now - last_sent).days
            
            should_draft = False
            next_stage = stage + 1
            
            # Custom Logic requested by User
            if is_investor:
                # Investor: Day 7, Day 17
                if stage == 0 and days_since_last >= 7:
                    should_draft = True
                elif stage == 1 and days_since_last >= 10: # 7 + 10 = 17
                    should_draft = True
            else:
                # Client: Day 2, Day 4
                if stage == 0 and days_since_last >= 2:
                    should_draft = True
                elif stage == 1 and days_since_last >= 2: # 2 + 2 = 4
                    should_draft = True
            
            if should_draft:
                logger.info(f"Generating Stage {next_stage} follow-up draft for lead {lead_id} ({lead['email']})")
                
                lead_name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "there"
                original_content = lead.get('last_outreach_body') or lead.get('email_draft') or "our previous outreach"
                
                ai_body = llm.generate_followup(lead_name, original_content, next_stage)
                
                # Inject Signature
                profile = get_sender_profile(str(lead['sender_id']))
                full_body = inject_signature(ai_body, profile, lead_id)
                
                cur.execute("""
                    UPDATE leads_raw 
                    SET followup_draft = %s,
                        followup_status = 'PENDING_APPROVAL',
                        followup_approved = FALSE,
                        updated_at = NOW()
                    WHERE id = %s
                """, (full_body, lead_id))
                conn.commit()
                
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in process_outreach_sequences: {e}")
