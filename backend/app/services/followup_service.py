import logging
from datetime import datetime, timedelta
from typing import List, Optional
import json

from app.database import get_db_connection
from app.services.email_service import send_email
from app.api.drafts import get_sender_profile, inject_signature
from app.services.llm_services import LLMService
from app.models.lead import add_activity_log

logger = logging.getLogger(__name__)

def get_followup_prompt() -> str:
    """Retrieves the active follow-up prompt from the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT content FROM prompts WHERE prompt_type = 'FOLLOWUP_GENERATION' AND is_active = TRUE LIMIT 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return row['content']
    except Exception as e:
        logger.error(f"Error fetching follow-up prompt: {e}")
    
    return "You are an AI assistant writing a gentle, professional follow-up email. \n\nOriginal Email Context: {original_content}\nRecipient: {lead_name}\n\nGuidelines:\n1. Be brief.\n2. Ask if they had any questions.\n3. Write the body now:"

def process_outreach_sequences():
    """
    Background worker function that finds leads due for follow-ups 
    (Day 2 and Day 4) and sends automated emails.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Find leads in 'ACTIVE' status, not responded, due for next stage
        # Stage 0 -> 1 (Day 2): 24h after initial outreach
        # Stage 1 -> 2 (Day 4): 48h after Day 2 outreach (72h total)
        cur.execute("""
            SELECT l.*, u.id as sender_id, u.email as sender_email, u.full_name as sender_name
            FROM leads_raw l
            JOIN users u ON l.user_id = u.id
            WHERE l.followup_status = 'ACTIVE' 
            AND l.is_responded = FALSE
            AND l.last_outreach_at <= NOW() - INTERVAL '1 minute' -- Reduced interval for testing, usually 24h
            ORDER BY l.last_outreach_at ASC
        """)
        
        leads_due = cur.fetchall()
        if not leads_due:
            cur.close()
            conn.close()
            return

        logger.info(f"Checking follow-ups for {len(leads_due)} active sequences.")
        llm = LLMService()
        
        for lead in leads_due:
            lead_id = lead['id']
            stage = lead['followup_stage'] or 0
            last_sent = lead['last_outreach_at']
            now = datetime.now()
            
            # --- Business Logic for Timing ---
            # For simplicity, we'll check the stage and time delta
            # Stage 0: Sent initial. Next is stage 1 (Day 2) after 24h.
            # Stage 1: Sent Day 2. Next is stage 2 (Day 4) after 48h.
            
            # TESTING MODE: 1 minute = 1 day
            time_since_last = (now - last_sent).total_seconds() / 60 
            
            should_send = False
            next_stage = stage + 1
            
            if stage == 0 and time_since_last >= 1: # Represents 24h
                should_send = True
            elif stage == 1 and time_since_last >= 2: # Represents 48h
                should_send = True
                
            if not should_send or stage >= 2:
                continue

            logger.info(f"Processing Stage {next_stage} follow-up for lead {lead_id} ({lead['email']})")
            
            # Generate Follow-up Content
            try:
                base_prompt = get_followup_prompt()
                lead_name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "there"
                
                final_prompt = base_prompt.format(
                    original_content=lead.get('email_draft') or "our previous outreach",
                    lead_name=lead_name
                )
                
                # Use LLM to generate just the body
                ai_response = llm.client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=500,
                    messages=[{"role": "user", "content": final_prompt}]
                )
                ai_body = "".join([b.text for b in ai_response.content if b.type == "text"]).strip()
                
                # Clean subject
                original_draft = lead.get('email_draft') or ""
                subject = "Following up"
                if "Subject: " in original_draft:
                    subject = "Re: " + original_draft.split("\n\n")[0].replace("Subject: ", "").strip()

                # Inject Signature
                profile = get_sender_profile(str(lead['sender_id']))
                full_body = inject_signature(ai_body, profile, lead_id)
                
                # Send Email
                success = send_email(
                    to_email=lead['email'],
                    subject=subject,
                    html_content=full_body.replace("\n", "<br>"),
                    from_email=lead['sender_email'],
                    from_name=lead['sender_name'],
                    lead_id=lead_id
                )
                
                if success:
                    # Update Lead State
                    cur.execute("""
                        UPDATE leads_raw 
                        SET followup_stage = %s, 
                            last_outreach_at = NOW(),
                            followup_status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (next_stage, 'COMPLETED' if next_stage >= 2 else 'ACTIVE', lead_id))
                    conn.commit()
                    
                    add_activity_log(lead_id, "FOLLOWUP_SENT", f"Automated Day {next_stage*2} follow-up sent.", "system")
                    logger.info(f"Follow-up Stage {next_stage} sent and logged for lead {lead_id}")
                
            except Exception as e:
                logger.error(f"Failed to generate/send follow-up for lead {lead_id}: {e}")
                conn.rollback()

        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in process_outreach_sequences: {e}")
