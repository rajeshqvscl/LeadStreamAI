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

FOLLOWUP_TEMPLATES = {
    "CLIENT": {
        1: "Hi {name},\n\nI hope you're having a good week.\n\nI'm just following up on my previous email regarding the partnership opportunity we discussed. Would love to hear your thoughts on this when you have a moment.",
        2: "Hi {name},\n\nFollowing up on my last note. I'm confident that our platform can add significant value to your current workflow, especially given your focus in the sector.\n\nAre you available for a brief 5-10 minute sync later this week to explore this?",
        3: "Hi {name},\n\nI've reached out a few times regarding our platform but haven't heard back, so I'll assume this isn't a priority for you at the moment.\n\nI'll stop my follow-ups for now, but feel free to reach out if your situation changes or if you have any questions in the future."
    },
    "INVESTOR": {
        1: "Dear {name},\n\nI hope you're doing well. I'm following up on the investment opportunity I shared last week regarding our agritech platform.\n\nPlease let me know if you have any questions or require further information.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are currently closing our latest round and have seen strong interest from strategic partners.\n\nGiven your expertise in this space, I'd value the opportunity to get your feedback on our current trajectory.",
        3: "Hi {name},\n\nI'm reaching out one last time to see if you'd like to discuss the opportunity. I understand you're busy, so I'll move this to the back burner if I don't hear from you.\n\nThanks again for your time and consideration."
    }
}

def get_template_followup(lead: dict, stage: int) -> str:
    """Returns a templated follow-up body based on lead type and stage."""
    lead_type_raw = str(lead.get('lead_type') or lead.get('sector') or lead.get('persona') or '').upper()
    type_key = "CLIENT" if ('CLIENT' in lead_type_raw or 'CUSTOMER' in lead_type_raw) else "INVESTOR"
    
    template = FOLLOWUP_TEMPLATES[type_key].get(stage, "Hi {name},\n\nFollowing up on my previous email.\n\nBest regards,")
    lead_name = f"{lead.get('first_name') or ''}".strip() or "there"
    return template.format(name=lead_name)

def generate_followup_preview(lead_id: int, user_id: int):
    """Generates a preview of the next follow-up email for the dashboard using templates."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT * FROM leads_raw WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        if not lead:
            return {"error": "Lead not found"}

        current_stage = lead['followup_stage'] or 0
        next_stage = current_stage + 1
        
        if next_stage > 3:
            return {"error": "Sequence already completed"}

        # Determine Lead Type
        lead_type_raw = str(lead.get('lead_type') or lead.get('sector') or lead.get('persona') or '').upper()
        type_key = "CLIENT" if ('CLIENT' in lead_type_raw or 'CUSTOMER' in lead_type_raw) else "INVESTOR"
        
        body = get_template_followup(lead, next_stage)
        
        # Clean subject
        subject = lead.get('last_outreach_subject') or "Following up"
        if not subject.startswith("Re:"):
            subject = "Re: " + subject

        # Inject Signature
        profile = get_sender_profile(str(user_id))
        full_body = inject_signature(body, profile, lead_id)
        
        return {
            "lead_id": lead_id,
            "next_stage": next_stage,
            "subject": subject,
            "body": body,
            "full_html": full_body.replace("\n", "<br>")
        }
    finally:
        cur.close()
        conn.close()

def process_outreach_sequences():
    """
    Background worker that identifies leads due for follow-ups.
    Client: Stage 1 (Day 2), Stage 2 (Day 4), Stage 3 (Day 10)
    Investor: Stage 1 (Day 7), Stage 2 (Day 14), Stage 3 (Day 30)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("""
            SELECT l.*, u.id as sender_id, u.email as sender_email, u.full_name as sender_name
            FROM leads_raw l
            JOIN users u ON l.user_id = u.id
            WHERE (l.followup_status = 'ACTIVE' OR l.followup_status IS NULL)
            AND l.email_status = 'SENT'
            AND COALESCE(l.is_responded, FALSE) = FALSE
            AND l.followup_stage < 3
            AND (l.followup_draft IS NULL OR l.followup_approved = TRUE)
            ORDER BY l.last_outreach_at ASC
        """)
        
        leads = cur.fetchall()
        if not leads:
            cur.close()
            conn.close()
            return

        for lead in leads:
            lead_id = lead['id']
            stage = lead['followup_stage'] or 0
            last_sent = lead['last_outreach_at']
            if not last_sent: continue
            
            # Determine Lead Type
            lead_type_raw = str(lead.get('lead_type') or lead.get('sector') or lead.get('persona') or '').upper()
            is_investor = not ('CLIENT' in lead_type_raw or 'CUSTOMER' in lead_type_raw)

            now = datetime.now()
            days_since_last = (now - last_sent).days
            
            should_draft = False
            next_stage = stage + 1
            
            if is_investor:
                # Investor: Day 7, Day 14, Day 30
                if stage == 0 and days_since_last >= 7:
                    should_draft = True
                elif stage == 1 and days_since_last >= 7: # 7 + 7 = 14
                    should_draft = True
                elif stage == 2 and days_since_last >= 16: # 14 + 16 = 30
                    should_draft = True
            else:
                # Client: Day 2, Day 4, Day 10
                if stage == 0 and days_since_last >= 2:
                    should_draft = True
                elif stage == 1 and days_since_last >= 2: # 2 + 2 = 4
                    should_draft = True
                elif stage == 2 and days_since_last >= 6: # 4 + 6 = 10
                    should_draft = True
            
            if should_draft:
                body = get_template_followup(lead, next_stage)
                
                # Inject Signature
                profile = get_sender_profile(str(lead['sender_id']))
                full_body = inject_signature(body, profile, lead_id)
                
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
