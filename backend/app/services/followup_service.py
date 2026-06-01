import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import json
import psycopg2.extras
import re
import threading

from app.database import get_db_connection
from app.services.email_service import send_email
from app.api.drafts import get_sender_profile, inject_signature, markdown_to_html
from app.services.llm_services import LLMService
from app.models.lead import add_activity_log

logger = logging.getLogger(__name__)

_followup_lock = threading.Lock()

def is_generic_followup(body: Optional[str]) -> bool:
    """Detects legacy, standard, or HTML-wrapped default placeholder follow-ups to allow dynamic healing."""
    if not body:
        return True
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]+>', '', body).strip().lower()
    if not cleaned:
        return True
    
    # Check for known generic fallback variations
    if "just following up on my previous email" in cleaned:
        return True
    if "let me know if you have any questions" in cleaned and "following up" in cleaned:
        return True
    if cleaned == "hi, just following up on my previous email. let me know if you have any questions!":
        return True
    if len(cleaned) < 120 and "following up" in cleaned and ("questions" in cleaned or "previous email" in cleaned):
        return True
        
    return False

FOLLOWUP_TEMPLATES = {
    "CLIENT": {
        1: "Hi {name},\n\nI hope you're having a good week.\n\nI'm just following up on my previous email regarding the collaboration we discussed. Would love to hear your thoughts on this when you have a moment.",
        2: "Hi {name},\n\nFollowing up on my last note. I'm confident that our platform can add significant value to your current workflow, especially given your focus in the sector.\n\nAre you available for a brief 5-10 minute sync later this week to explore this?",
        3: "Hi {name},\n\nI've reached out a few times regarding our platform but haven't heard back, so I'll assume this isn't a priority for you at the moment.\n\nI'll stop my follow-ups for now, but feel free to reach out if your situation changes or if you have any questions in the future."
    },
    "INVESTOR_AGRITECH": {
        1: "Dear {name},\n\nI hope you're doing well. I'm following up on the investment opportunity I shared last week regarding our agritech platform.\n\nPlease let me know if you have any questions or require further information.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are currently closing our latest round and have seen strong interest from strategic partners.\n\nGiven your expertise in this space, I'd value the opportunity to get your feedback on our current trajectory.",
        3: "Hi {name},\n\nI'm reaching out one last time to see if you'd like to discuss the opportunity. I understand you're busy, so I'll move this to the back burner if I don't hear from you.\n\nThanks again for your time and consideration."
    },
    "INVESTOR_AI_HIRING": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the AI Hiring Infrastructure platform teaser shared earlier. Please let me know if you have reviewed it or require any additional information for evaluation.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing exceptional enterprise traction for our AI Hiring Infrastructure.\n\nGiven your focus in this domain, would you be open to a brief 5-10 minute call to discuss this further?",
        3: "Hi {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration."
    },
    "INVESTOR_HEALTHTECH": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the HealthTech opportunity I shared regarding our AI-enabled diagnostics platform.\n\nPlease let me know if you have any questions or require further information.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing strong traction and expanding our lab network significantly.\n\nGiven your focus in the healthcare space, I'd value the opportunity to get your feedback on our current trajectory. Are you available for a brief sync?",
        3: "Hi {name},\n\nI'm reaching out one last time to see if you'd like to discuss the opportunity. I understand you're busy, so I'll move this to the back burner if I don't hear from you.\n\nThanks again for your time and consideration."
    },
    "INVESTOR_DEFENCE": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the Defence Deeptech & AI Systems opportunity (iDEX Prime Winner) I shared earlier.\n\nPlease let me know if you have reviewed it or require any additional information for evaluation.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing exceptional traction and interest from key strategic partners in the deeptech and national security ecosystem.\n\nGiven your focus in this domain, would you be open to a brief 5-10 minute call to discuss this further?",
        3: "Hi {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration."
    },
    "INVESTOR_GENERIC": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the investment opportunity teaser I shared earlier.\n\nPlease let me know if you have reviewed it or require any additional information for evaluation.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing strong interest and strategic progress across our core milestones.\n\nWould you be open to a brief 5-10 minute sync this week to share a quick update and discuss further?",
        3: "Hi {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration."
    },
    "INVESTOR_PALAK_ADVISORY": {
        1: "Dear {name},\n\nI hope you are well.\n\nJust following up on my previous email. We would value the opportunity to connect and understand your growth roadmap and any potential capital/funding priorities that may be ahead.\n\nWould you be open to a short video call? Happy to coordinate as per your availability.\n\nLooking forward to hearing from you.",
        2: "Dear {name},\n\nJust following up on my earlier note.\n\nGiven your growth journey, we thought it may be worthwhile to connect and exchange perspectives around future expansion and funding opportunities.\n\nPlease let us know a suitable time for a brief discussion if this would be of interest.\n\nLooking forward to connecting.",
        3: "Dear {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration."
    },
    "INVESTOR_KAJAL_HEALTH_ECOSYSTEM": {
        1: """Dear {name},

I hope you're doing well.

I wanted to follow up on our earlier note regarding the **Seed Round opportunity in a preventive health ecosystem platform** building India's diagnostics infrastructure layer.

Since our last outreach, the company has continued to demonstrate strong momentum:

- **7,000+ diagnostic orders completed**
- **300+ labs onboarded** across Delhi NCR
- **₹89L+ revenue generated to date**
- **₹2.58 Cr annualized revenue run rate**

The platform is positioned at the intersection of **diagnostics, AI-driven insights, and continuous preventive health monitoring**, addressing a large and underserved market opportunity.

The company is currently raising a **$1M Seed Round** to scale technology, expand the diagnostics network, and strengthen institutional partnerships.

Happy to share the detailed pitch deck and additional information.

Looking forward to your thoughts.""",
        2: """Dear {name},

I wanted to share updates on the **Seed Round opportunity in a preventive health ecosystem platform** building India's diagnostics infrastructure layer.

Since our last outreach, the company has continued to demonstrate strong momentum:

- **7,000+ diagnostic orders completed**
- **300+ labs onboarded** across Delhi NCR
- **₹89L+ revenue generated to date**
- **₹2.58 Cr annualized revenue run rate**

The platform is positioned at the intersection of **diagnostics, AI-driven insights, and continuous preventive health monitoring**, addressing a large and underserved market opportunity.

The company is currently raising a **$1M Seed Round** to scale technology, expand the diagnostics network, and strengthen institutional partnerships.

Happy to share the detailed pitch deck and additional information.

Looking forward to your thoughts.""",
        3: """Dear {name},

I hope this finds you well.

I'm reaching out one final time regarding the **Seed Round for our AI-enabled preventive health ecosystem platform** — with 300+ labs, 7,000+ orders, and ₹2.58 Cr ARR, the company has shown strong early traction.

If the timing isn't right or this doesn't align with your current focus, I completely understand — I'll step back from my follow-ups.

However, if circumstances change or you'd like to revisit this opportunity, please don't hesitate to reach out. We'd be happy to share the full deck or connect at your convenience.

Thank you sincerely for your time and consideration."""
    }
}

def get_template_followup(lead: dict, stage: int) -> str:
    """Returns the standardized, high-performance follow-up template for the lead's sector and stage."""
    lead_name = f"{lead.get('first_name') or ''}".strip() or "there"
    
    # CUSTOM TEMPLATE FOLLOW-UPS: If the lead used a custom draft template that has follow-up content,
    # use that instead of hardcoded templates
    draft_template = str(lead.get('draft_template_used') or '').strip()
    if draft_template:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT followup_1, followup_2, followup_3 FROM prompts WHERE name = %s AND prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE", (draft_template,))
            tpl = cur.fetchone()
            cur.close()
            conn.close()
            if tpl:
                custom_body = tpl.get(f'followup_{stage}')
                if custom_body:
                    # Replace placeholders
                    custom_body = custom_body.replace("{{First Name}}", lead_name)
                    return custom_body
        except Exception:
            pass
    
    # Fallback: Check draft_template_used for known campaign overrides
    draft_template = str(lead.get('draft_template_used') or '').strip()
    
    # Also check subject as fallback (some leads may not have draft_template_used saved)
    orig_subj = get_original_outreach_subject(lead) or ""
    
    if draft_template == 'palak_mam_corporate_advisory' or "corporate advisory" in orig_subj.lower():
        campaign_key = "INVESTOR_PALAK_ADVISORY"
    elif draft_template == 'kajal_mam_health_ecosystem':
        campaign_key = "INVESTOR_KAJAL_HEALTH_ECOSYSTEM"
    else:
        lead_type_raw = str(lead.get('lead_type') or lead.get('sector') or lead.get('persona') or '').upper()
        type_key = "CLIENT" if ('CLIENT' in lead_type_raw or 'CUSTOMER' in lead_type_raw) else "INVESTOR"
        
        if type_key == "INVESTOR":
            # Dynamic campaign detection (AI Hiring vs HealthTech vs Agritech vs Defence vs Generic)
            original_subject = get_original_outreach_subject(lead) or ""
            draft_text = lead.get('email_draft') or ""
            persona_text = lead.get('persona') or ""
            sector_text = lead.get('sector') or ""
            
            is_ai_hiring = (
                "hiring" in original_subject.lower() or 
                "hiring" in draft_text.lower() or 
                "hiring" in persona_text.lower() or 
                "hiring" in sector_text.lower() or
                "recruitment" in original_subject.lower() or 
                "recruitment" in draft_text.lower()
            )

            is_healthtech = (
                "health" in original_subject.lower() or
                "health" in draft_text.lower() or
                "health" in persona_text.lower() or
                "health" in sector_text.lower() or
                "diagnostic" in original_subject.lower() or
                "diagnostic" in draft_text.lower()
            )
            
            is_defence = (
                "defence" in original_subject.lower() or
                "defence" in draft_text.lower() or
                "defence" in persona_text.lower() or
                "defence" in sector_text.lower() or
                "deeptech" in original_subject.lower() or
                "deeptech" in draft_text.lower() or
                "idex" in original_subject.lower() or
                "idex" in draft_text.lower()
            )
            
            is_agritech = (
                "agritech" in original_subject.lower() or
                "agritech" in draft_text.lower() or
                "agritech" in persona_text.lower() or
                "agritech" in sector_text.lower() or
                "climate" in original_subject.lower() or
                "climate" in draft_text.lower()
            )
            
            is_palak_advisory = (
                not draft_template and (
                    "corporate advisory" in original_subject.lower() or
                    ("corporate advisory" in draft_text.lower() and "m&a" not in draft_text.lower() and "partnership" not in draft_text.lower())
                )
            )

            if is_palak_advisory:
                campaign_key = "INVESTOR_PALAK_ADVISORY"
            elif is_ai_hiring:
                campaign_key = "INVESTOR_AI_HIRING"
            elif is_healthtech:
                campaign_key = "INVESTOR_HEALTHTECH"
            elif is_defence:
                campaign_key = "INVESTOR_DEFENCE"
            elif is_agritech:
                campaign_key = "INVESTOR_AGRITECH"
            else:
                campaign_key = "INVESTOR_GENERIC"
        else:
            campaign_key = "CLIENT"
        
    template = FOLLOWUP_TEMPLATES[campaign_key].get(stage, "Hi {name},\n\nFollowing up on my previous email.\n\nBest regards,")
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
        
        # Use saved draft if exists, unless it is empty or matches a generic default fallback string
        body = lead.get('followup_draft')
        if is_generic_followup(body):
            body = get_template_followup(lead, next_stage)
        
        # Clean subject
        orig_subject = get_original_outreach_subject(lead)
        subject = f"Re: {orig_subject}"

        # Inject Signature
        profile = get_sender_profile(str(user_id))
        name = profile.get('full_name') or profile.get('username') or 'Team'
        name = " ".join([p.capitalize() for p in name.split()])
        
        # Convert plain text to HTML with proper signature spacing
        body_with_sig = body + f"\n\n--\nRegards,\n{name}"
        full_body = markdown_to_html(body_with_sig)

        return {
            "lead_id": lead_id,
            "next_stage": next_stage,
            "subject": subject,
            "body": body,
            "full_html": full_body
        }
    finally:
        cur.close()
        conn.close()


def _is_working_hours():
    """Returns True if current IST time is Mon-Fri 10AM-5PM."""
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST).replace(tzinfo=None)
    if now.weekday() >= 5:
        return False
    if now.hour < 10 or now.hour >= 17:
        return False
    return True

def _recheck_working_hours():
    """Same check but returns an early-stop reason string if outside hours/weekend."""
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST).replace(tzinfo=None)
    if now.weekday() >= 5:
        return f"Weekend — {now.strftime('%A %Y-%m-%d %H:%M:%S IST')}"
    if now.hour < 10 or now.hour >= 17:
        return f"Outside hours — {now.strftime('%Y-%m-%d %H:%M:%S IST')}"
    return None

def process_outreach_sequences():
    """
    Background worker that identifies leads due for follow-ups.
    Enforces 'Working Days Only' and sequential 'Drip Sending' with a 30-second gap
    and enforces a daily limit per user (default 200) to prevent spam flagging.
    """
    if not _followup_lock.acquire(blocking=False):
        logger.info("process_outreach_sequences already running — skipping overlapping run")
        return
    try:
        if not _is_working_hours():
            IST = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(IST).replace(tzinfo=None)
            logger.info(f"Outreach paused: Weekend/hours protection active (IST). Current: {now.strftime('%A %Y-%m-%d %H:%M:%S')}")
            return

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

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

        user_leads = {}
        for lead in leads:
            uid = lead['sender_id']
            if uid not in user_leads:
                user_leads[uid] = []
            user_leads[uid].append(lead)

        IST = timezone(timedelta(hours=5, minutes=30))

        for uid, group in user_leads.items():
            first_lead = group[0]
            logger.info(f"Auto-pilot checking user {uid} ({first_lead['sender_name']} / {first_lead['sender_email']}): auto_followup={first_lead['auto_followup']}, has_token={bool(first_lead['google_refresh_token'])}")
            if not first_lead['auto_followup'] or not first_lead['google_refresh_token']:
                logger.info(f"Skipping auto-pilot for user {uid}: auto-followup disabled or Gmail not linked.")
                continue

            daily_limit = first_lead['outreach_daily_limit'] or 200

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM activity_log
                WHERE user_id = %s
                AND action IN ('AUTO_FOLLOWUP_SENT', 'EMAIL_SENT')
                AND created_at >= NOW() - INTERVAL '1 day'
            """, (uid,))
            row_count = cur.fetchone()
            sent_today = list(row_count.values())[0] if row_count else 0
            cur.close()
            conn.close()

            remaining_allowance = max(0, daily_limit - sent_today)
            if remaining_allowance <= 0:
                logger.info(f"User {uid} has hit their daily outreach limit ({sent_today}/{daily_limit} sent today).")
                continue

            sent_count = 0
            for lead in group:
                # Re-check working hours before EVERY send to prevent weekend/hour bleed
                reason = _recheck_working_hours()
                if reason:
                    logger.info(f"Outreach paused mid-batch: {reason}")
                    break

                if sent_count >= remaining_allowance:
                    logger.info(f"Daily quota reached for user {uid} during sequence run.")
                    break

                try:
                    lead = dict(lead)
                    lead_id = lead['id']
                    stage = lead['followup_stage'] or 0
                    last_sent = lead['last_outreach_at']
                    if not last_sent:
                        continue

                    if last_sent.tzinfo:
                        last_sent_ist = last_sent.astimezone(IST).replace(tzinfo=None)
                    else:
                        last_sent_ist = last_sent.replace(tzinfo=timezone.utc).astimezone(IST).replace(tzinfo=None)

                    now = datetime.now(IST).replace(tzinfo=None)
                    lead_type_raw = str(lead.get('lead_type') or lead.get('company_name') or lead.get('sector') or lead.get('persona') or '').upper()
                    investor_kw = ["VENTURE", "CAPITAL", "EQUITY", "INVEST", "PARTNER", "ASSET", "FAMILY OFFICE", "ANGEL", "CIRCLE", "NETWORK", "FUND", "VC", "PE"]
                    is_investor = any(kw in lead_type_raw for kw in investor_kw) or not ('CLIENT' in lead_type_raw or 'CUSTOMER' in lead_type_raw)
                    days_since_last = (now - last_sent_ist).days

                    should_action = False
                    next_stage = stage + 1

                    if is_investor:
                        if (stage == 0 and days_since_last >= 7) or (stage == 1 and days_since_last >= 14) or (stage == 2 and days_since_last >= 30):
                            should_action = True
                    else:
                        if (stage == 0 and days_since_last >= 2) or (stage == 1 and days_since_last >= 4) or (stage == 2 and days_since_last >= 10):
                            should_action = True

                    if not should_action:
                        continue

                    # Skip Defence leads (user explicitly doesn't want follow-ups for Defence)
                    orig_subj = get_original_outreach_subject(lead) or ""
                    draft_text = lead.get('email_draft') or ""
                    persona_text = lead.get('persona') or ""
                    sector_text = lead.get('sector') or ""
                    is_defence = (
                        "defence" in orig_subj.lower()
                        or "defence" in draft_text.lower()
                        or "defence" in persona_text.lower()
                        or "defence" in sector_text.lower()
                        or "deeptech" in orig_subj.lower()
                        or "deeptech" in draft_text.lower()
                        or "idex" in orig_subj.lower()
                        or "idex" in draft_text.lower()
                    )
                    if is_defence:
                        logger.info(f"Lead {lead_id} is Defence — skipping per user request")
                        continue

                    # Re-verify stage, status, and auto-pilot (prevents sends after user stops follow-up)
                    try:
                        verify_conn = get_db_connection()
                        verify_cur = verify_conn.cursor()
                        verify_cur.execute("""
                            SELECT l.followup_stage, l.followup_status, l.is_responded, u.auto_followup
                            FROM leads_raw l
                            JOIN users u ON l.user_id = u.id
                            WHERE l.id = %s
                        """, (lead_id,))
                        verify_row = verify_cur.fetchone()
                        verify_cur.close()
                        verify_conn.close()
                        
                        if verify_row:
                            current_stage = verify_row['followup_stage'] if isinstance(verify_row, dict) else verify_row[0]
                            current_status = verify_row['followup_status'] if isinstance(verify_row, dict) else verify_row[1]
                            current_responded = verify_row['is_responded'] if isinstance(verify_row, dict) else verify_row[2]
                            current_auto = verify_row['auto_followup'] if isinstance(verify_row, dict) else verify_row[3]
                            
                            if current_stage is not None and current_stage != stage:
                                logger.info(f"Lead {lead_id} stage changed from {stage} to {current_stage} — skipping")
                                continue
                            if current_status != 'ACTIVE':
                                logger.info(f"Lead {lead_id} followup_status is '{current_status}' — skipping")
                                continue
                            if current_responded:
                                logger.info(f"Lead {lead_id} already responded — skipping")
                                continue
                            if not current_auto:
                                logger.info(f"Lead {lead_id} auto-pilot turned off — skipping")
                                continue
                    except Exception as verify_err:
                        logger.warning(f"Re-verify failed for lead {lead_id}: {verify_err}")

                    existing_thread_id = lead.get('gmail_thread_id')
                    existing_msg_id = lead.get('gmail_message_id')

                    if not existing_thread_id:
                        try:
                            import re as _re
                            from app.services.google_service import get_gmail_service
                            heal_service = get_gmail_service(int(uid))
                            if heal_service:
                                q = f"in:sent to:{lead['email']}"
                                heal_results = heal_service.users().messages().list(
                                    userId='me', q=q, maxResults=10
                                ).execute()
                                heal_msgs = heal_results.get('messages', [])
                                if heal_msgs:
                                    heal_msg = heal_service.users().messages().get(
                                        userId='me',
                                        id=heal_msgs[-1]['id'],
                                        format='metadata',
                                        metadataHeaders=['Message-ID', 'Message-Id', 'message-id', 'Subject']
                                    ).execute()
                                    heal_thread_id = heal_msg.get('threadId')
                                    heal_headers = heal_msg.get('payload', {}).get('headers', [])
                                    heal_msg_id = next(
                                        (h['value'] for h in heal_headers if h['name'].lower() == 'message-id'),
                                        f"<{heal_msgs[-1]['id']}@mail.gmail.com>"
                                    )
                                    heal_subject = next(
                                        (h['value'] for h in heal_headers if h['name'].lower() == 'subject'),
                                        None
                                    )
                                    if heal_thread_id:
                                        existing_thread_id = heal_thread_id
                                        existing_msg_id = heal_msg_id
                                        if heal_subject:
                                            lead['first_outreach_subject'] = heal_subject

                                        heal_conn = get_db_connection()
                                        heal_cur = heal_conn.cursor()
                                        heal_cur.execute("""
                                            UPDATE leads_raw
                                            SET gmail_thread_id = %s,
                                                gmail_message_id = %s,
                                                first_outreach_subject = COALESCE(first_outreach_subject, %s),
                                                updated_at = NOW()
                                            WHERE id = %s
                                        """, (heal_thread_id, heal_msg_id, heal_subject, lead_id))
                                        heal_conn.commit()
                                        heal_cur.close()
                                        heal_conn.close()
                        except Exception as heal_err:
                            logger.warning(f"On-the-fly thread heal failed for lead {lead_id}: {heal_err}")

                    # Final duplicate guard: check activity_log for existing follow-up at this stage
                    try:
                        dup_conn = get_db_connection()
                        dup_cur = dup_conn.cursor()
                        dup_cur.execute(
                            "SELECT COUNT(*) FROM activity_log WHERE lead_id = %s AND action = 'AUTO_FOLLOWUP_SENT' AND details LIKE %s",
                            (lead_id, f"Stage {next_stage}%")
                        )
                        dup_count = list(dup_cur.fetchone().values())[0]
                        dup_cur.close()
                        dup_conn.close()
                        if dup_count > 0:
                            logger.info(f"Lead {lead_id}: Stage {next_stage} already sent ({dup_count}x in log) — skipping duplicate")
                            continue
                    except Exception as dup_err:
                        logger.warning(f"Duplicate check failed for lead {lead_id}: {dup_err}")

                    orig_subject = get_original_outreach_subject(lead)
                    subject = f"Re: {orig_subject}"

                    body = lead.get('followup_draft')
                    if is_generic_followup(body):
                        body = get_template_followup(lead, next_stage)
                    profile = get_sender_profile(str(uid))
                    name = profile.get('full_name') or profile.get('username') or 'Team'
                    name = " ".join([p.capitalize() for p in name.split()])
                    first_name = name.split()[0] if name else name

                    body_with_sig = body + f"\n\n--\nRegards,\n{first_name}"
                    full_body = markdown_to_html(body_with_sig)

                    success, msg, new_thread_id, new_rfc_msg_id = send_email(
                        to_email=lead['email'],
                        subject=subject,
                        html_content=full_body,
                        from_email=lead['sender_email'],
                        from_name=lead['sender_name'],
                        user_id=str(uid),
                        thread_id=existing_thread_id,
                        in_reply_to=existing_msg_id
                    )

                    if success:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("""
                            UPDATE leads_raw 
                            SET followup_stage = %s, followup_status = 'ACTIVE', email_status = 'SENT',
                                last_outreach_at = NOW(), last_outreach_subject = %s,
                                gmail_thread_id = COALESCE(%s, gmail_thread_id),
                                gmail_message_id = COALESCE(%s, gmail_message_id),
                                updated_at = NOW()
                            WHERE id = %s AND followup_stage = %s
                        """, (next_stage, subject, new_thread_id, new_rfc_msg_id, lead_id, stage))
                        conn.commit()
                        updated_count = cur.rowcount
                        cur.close()
                        conn.close()

                        if updated_count == 0:
                            logger.warning(f"Lead {lead_id} stage already changed — email sent but stage not updated to avoid duplicate")
                            continue

                        add_activity_log(lead_id, "AUTO_FOLLOWUP_SENT", f"Stage {next_stage} auto-sent", "system", uid)
                        sent_count += 1

                        logger.info(f"Auto-followup sent from {first_lead['sender_name']} ({first_lead['sender_email']}) to {lead['email']}. Enforcing 30s cool-down...")
                        time.sleep(30)
                    else:
                        logger.error(f"Auto-Pilot failed for {lead['email']}: {msg}")
                except Exception as ex:
                    logger.error(f"Error dispatching auto-followup for lead {lead.get('id')}: {ex}")
    except Exception as e:
        logger.error(f"Error in process_outreach_sequences: {e}")
    finally:
        _followup_lock.release()
