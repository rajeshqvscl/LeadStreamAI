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

def get_original_outreach_subject(lead: dict) -> str:
    """Helper to extract the genuine original email subject to maintain correct threading."""
    # 1. Try first_outreach_subject
    subject = lead.get('first_outreach_subject')
    if subject and subject.strip() and subject.lower() != "following up":
        subj = subject.strip()
        while subj.lower().startswith("re:"):
            subj = subj[3:].strip()
        if subj and subj.lower() != "following up":
            return subj
            
    # 2. Try last_outreach_subject
    subject = lead.get('last_outreach_subject')
    if subject and subject.strip() and subject.lower() != "following up":
        subj = subject.strip()
        while subj.lower().startswith("re:"):
            subj = subj[3:].strip()
        if subj and subj.lower() != "following up":
            return subj
            
    # 3. Parse from email_draft
    draft = lead.get('email_draft') or ""
    if draft and "subject:" in draft.lower():
        lines = draft.split("\n")
        for line in lines:
            if line.strip().lower().startswith("subject:"):
                subj_parsed = line.split(":", 1)[1].strip()
                while subj_parsed.lower().startswith("re:"):
                    subj_parsed = subj_parsed[3:].strip()
                if subj_parsed and subj_parsed.lower() != "following up":
                    return subj_parsed
                    
    # 4. Fallback to sector/company custom professional subject line
    company = lead.get('company_name') or "your company"
    sector = lead.get('sector') or "investment"
    return f"investment opportunity - {company}"

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
        
        # Use saved draft if exists, otherwise generate from template
        body = lead.get('followup_draft')
        if not body:
            body = get_template_followup(lead, next_stage)
        
        # Clean subject
        orig_subject = get_original_outreach_subject(lead)
        subject = f"Re: {orig_subject}"

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
    Enforces 'Working Days Only' and sequential 'Drip Sending' with a 30-second gap
    and enforces a daily limit per user (default 200) to prevent spam flagging.
    """
    try:
        # SAFETY: Only send on working days (Mon-Fri)
        now = datetime.now()
        if now.weekday() >= 5: # 5 = Saturday, 6 = Sunday
            logger.info("Outreach paused: Weekend protection active.")
            return

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Fetch leads due for followup + the user's auto-pilot settings
        cur.execute("""
            SELECT l.*, u.id as sender_id, u.email as sender_email, u.full_name as sender_name,
                   u.auto_followup, u.outreach_daily_limit, u.google_refresh_token
            FROM leads_raw l
            JOIN users u ON l.user_id = u.id
            WHERE l.followup_status = 'ACTIVE'
            AND l.email_status = 'SENT'
            AND COALESCE(l.is_responded, FALSE) = FALSE
            AND l.followup_stage < 3
            ORDER BY l.last_outreach_at ASC
        """)
        
        leads = cur.fetchall()
        cur.close()
        conn.close()

        if not leads: 
            return

        import time
        from app.services.email_service import send_email

        # Group leads by user so we can track and enforce daily limit per sender
        user_leads = {}
        for lead in leads:
            uid = lead['sender_id']
            if uid not in user_leads:
                user_leads[uid] = []
            user_leads[uid].append(lead)

        for uid, group in user_leads.items():
            first_lead = group[0]
            # Check user auto_followup flag and Gmail link
            if not first_lead['auto_followup'] or not first_lead['google_refresh_token']:
                logger.info(f"Skipping auto-pilot for user {uid}: auto-followup disabled or Gmail not linked.")
                continue

            # Fetch the user's daily sending limit (default to 200)
            daily_limit = first_lead['outreach_daily_limit'] or 200
            
            # Count how many emails this user has already sent today (last 24 hours)
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM activity_log
                WHERE user_id = %s
                AND action IN ('AUTO_FOLLOWUP_SENT', 'EMAIL_SENT')
                AND created_at >= NOW() - INTERVAL '1 day'
            """, (uid,))
            sent_today = cur.fetchone()[0] or 0
            cur.close()
            conn.close()

            remaining_allowance = max(0, daily_limit - sent_today)
            if remaining_allowance <= 0:
                logger.info(f"User {uid} has hit their daily outreach limit ({sent_today}/{daily_limit} sent today).")
                continue

            logger.info(f"User {uid} has {remaining_allowance} emails remaining for today's quota ({sent_today}/{daily_limit} sent).")

            # Process sequentially with strict 30-second delay gap
            sent_count = 0
            for lead in group:
                if sent_count >= remaining_allowance:
                    logger.info(f"Daily quota reached for user {uid} during sequence run.")
                    break

                try:
                    lead_id = lead['id']
                    stage = lead['followup_stage'] or 0
                    last_sent = lead['last_outreach_at']
                    if not last_sent: 
                        continue

                    # Stage schedule check
                    lead_type_raw = str(lead.get('lead_type') or lead.get('company_name') or lead.get('sector') or lead.get('persona') or '').upper()
                    investor_kw = ["VENTURE", "CAPITAL", "EQUITY", "INVEST", "PARTNER", "ASSET", "FAMILY OFFICE", "ANGEL", "CIRCLE", "NETWORK", "FUND", "VC", "PE"]
                    is_investor = any(kw in lead_type_raw for kw in investor_kw) or not ('CLIENT' in lead_type_raw or 'CUSTOMER' in lead_type_raw)
                    days_since_last = (now - last_sent).days

                    should_action = False
                    next_stage = stage + 1

                    if is_investor:
                        if (stage == 0 and days_since_last >= 7) or (stage == 1 and days_since_last >= 7) or (stage == 2 and days_since_last >= 16):
                            should_action = True
                    else:
                        if (stage == 0 and days_since_last >= 2) or (stage == 1 and days_since_last >= 2) or (stage == 2 and days_since_last >= 6):
                            should_action = True

                    if not should_action: 
                        continue

                    body = get_template_followup(lead, next_stage)
                    profile = get_sender_profile(str(uid))
                    full_body = inject_signature(body, profile, lead_id)
                    
                    # Subject line continuation with Re: prefix
                    orig_subject = get_original_outreach_subject(lead)
                    subject = f"Re: {orig_subject}"

                    logger.info(f"Auto-dispatching lead {lead_id} ({lead['email']}) for User {uid}. Subject: {subject}")
                    
                    # Dispatch Email
                    success, msg, new_thread_id, new_rfc_msg_id = send_email(
                        to_email=lead['email'],
                        subject=subject,
                        html_content=full_body.replace("\n", "<br>"),
                        from_email=lead['sender_email'],
                        from_name=lead['sender_name'],
                        user_id=str(uid),
                        thread_id=lead.get('gmail_thread_id'),
                        in_reply_to=lead.get('gmail_message_id')
                    )

                    if success:
                        # Update Database Row
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("""
                            UPDATE leads_raw 
                            SET followup_stage = %s, followup_status = 'ACTIVE', email_status = 'SENT',
                                last_outreach_at = NOW(), last_outreach_subject = %s,
                                gmail_thread_id = COALESCE(%s, gmail_thread_id),
                                gmail_message_id = COALESCE(%s, gmail_message_id),
                                updated_at = NOW()
                            WHERE id = %s
                        """, (next_stage, subject, new_thread_id, new_rfc_msg_id, lead_id))
                        conn.commit()
                        cur.close()
                        conn.close()

                        add_activity_log(lead_id, "AUTO_FOLLOWUP_SENT", f"Stage {next_stage} auto-sent", "system", uid)
                        sent_count += 1
                        
                        # ENFORCE USER'S REQUEST: 30-second delay gap between consecutive sends to prevent spam flagging
                        logger.info("Email sent successfully! Enforcing a 30-second cool-down gap before the next email...")
                        time.sleep(30)
                    else:
                        logger.error(f"Auto-Pilot failed for {lead['email']}: {msg}")
                except Exception as ex:
                    logger.error(f"Error dispatching auto-followup for lead {lead.get('id')}: {ex}")

    except Exception as e:
        logger.error(f"Error in process_outreach_sequences: {e}")
