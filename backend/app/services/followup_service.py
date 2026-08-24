import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import json
import psycopg2.extras
import re

from app.database import get_db_connection
from app.services.email_service import get_user_email_font, get_user_email_font_size
from app.api.drafts import markdown_to_html, get_followup_signature_markdown
from app.models.lead import add_activity_log
from app.core.followup.engine import get_followup_engine, FollowUpAction
from app.core.pipeline.claims import LeadClaimer
from app.core.pipeline.state_machine import get_pipeline
from app.email_engine.producer import get_email_producer

logger = logging.getLogger(__name__)


def is_generic_followup(body: Optional[str]) -> bool:
    """Detects legacy, standard, or HTML-wrapped default placeholder follow-ups to allow dynamic healing."""
    if not body:
        return True
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]+>', '', body).strip().lower()
    if not cleaned:
        return True
    
    # Check if this is an original email draft (has Subject: line or is too long)
    if "subject:" in cleaned:
        return True
    if len(cleaned) > 500:
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
    if "just following up on the climate agritech platform opportunity shared earlier" in cleaned:
        return True
    
    return False


def process_outreach_sequences():
    """
    Background worker that identifies leads due for follow-ups.
    Uses FollowUpEngine for evaluation and EmailProducer for queueing.
    """
    from app.core.followup.engine import get_followup_engine
    from app.email_engine.producer import get_email_producer
    from app.core.pipeline.scheduler import get_scheduler_config
    from app.core.pipeline.state_machine import get_pipeline
    from app.database import get_db_connection
    import psycopg2.extras
    
    config = get_scheduler_config()
    pipeline = get_pipeline()
    engine = get_followup_engine()
    producer = get_email_producer()
    
    if not config.is_working_hours_now():
        logger.info("Outreach paused: Outside working hours")
        return
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Query leads that might need follow-up (broad filter, engine does precise check)
        cur.execute("""
            SELECT l.*, u.id as sender_id, u.email as sender_email, u.full_name as sender_name,
                   u.auto_followup, u.outreach_daily_limit, u.google_refresh_token,
                   u.email_font, u.email_font_size
            FROM leads_raw l
            JOIN users u ON l.user_id = u.id
            WHERE l.followup_status = 'ACTIVE'
              AND l.email_status IN ('SENT', 'OPENED', 'CLICKED')
              AND COALESCE(l.is_responded, FALSE) = FALSE
              AND l.replied_at IS NULL
              AND COALESCE(l.reply_intent, '') NOT IN ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED', 'NEEDS_MORE_INFO')
              AND l.followup_stage < 3
              AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
              AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
              AND l.email NOT IN (SELECT email FROM unsubscribe_list)
            ORDER BY l.user_id, LOWER(l.email), l.last_outreach_at ASC
        """)

        leads = cur.fetchall()
        cur.close()

        if not leads:
            conn.close()
            return

        # Group by user for per-user limits
        user_leads = {}
        for lead in leads:
            uid = lead['sender_id']
            if uid not in user_leads:
                user_leads[uid] = []
            user_leads[uid].append(dict(lead))

        for uid, group in user_leads.items():
            first_lead = group[0]
            logger.info(f"Auto-pilot checking user {uid} ({first_lead['sender_name']} / {first_lead['sender_email']}): auto_followup={first_lead['auto_followup']}, has_token={bool(first_lead['google_refresh_token'])}")
            if not first_lead['auto_followup'] or not first_lead['google_refresh_token']:
                logger.info(f"Skipping auto-pilot for user {uid}: auto-followup disabled or Gmail not linked.")
                continue

            sent_count = 0
            max_per_cycle = config.followup_settings.max_auto_sends_per_cycle if hasattr(config, 'followup_settings') else 200
            
            for lead in group:
                if sent_count >= max_per_cycle:
                    logger.info(f"Per-cycle cap ({max_per_cycle}) reached for user {uid} — remaining leads picked up next cycle.")
                    break

                try:
                    # Evaluate if lead is due for follow-up
                    action = engine.evaluate(lead)
                    
                    if not action.should_send:
                        continue
                    
                    # Check pipeline state transition
                    lead_obj = type('Lead', (), lead)()
                    lead_obj.pipeline_state = lead.get('pipeline_state', 'FOLLOWUP_ACTIVE')
                    lead_obj.followup_stage = lead.get('followup_stage', 0)
                    lead_obj.lead_type = action.lead_type
                    lead_obj.auto_followup = lead.get('auto_followup', True)
                    lead_obj.google_refresh_token = lead.get('google_refresh_token')
                    
                    if not pipeline.can_transition(lead_obj.pipeline_state, 'FOLLOWUP_ACTIVE', lead_obj):
                        logger.info(f"Lead {lead['id']} cannot transition to FOLLOWUP_ACTIVE")
                        continue
                    
                    # Build email content with signature
                    followup_sig = get_followup_signature_markdown(str(uid))
                    body_with_sig = action.body
                    if followup_sig:
                        body_with_sig = body_with_sig.rstrip() + f"\n\n{followup_sig}"
                    
                    # Convert to HTML
                    from app.api.drafts import markdown_to_html
                    from app.services.email_service import get_user_image_width, get_user_image_height
                    email_font = lead.get('email_font') or 'sans-serif'
                    email_font_size = lead.get('email_font_size') or '15px'
                    image_width = get_user_image_width(uid)
                    image_height = get_user_image_height(uid)
                    html_content = markdown_to_html(body_with_sig, font_family=email_font, font_size=email_font_size, image_width=image_width, image_height=image_height)
                    
                    # Enqueue via producer
                    job_id = producer.send_followup(
                        lead_id=lead['id'],
                        stage=action.stage,
                        user_id=uid,
                        to_email=lead['email'],
                        subject=action.subject,
                        html_content=html_content,
                        from_email=lead['sender_email'],
                        from_name=lead['sender_name'],
                        thread_id=lead.get('gmail_thread_id'),
                        in_reply_to=lead.get('gmail_message_id'),
                        template_name=action.campaign,
                    )
                    
                    logger.info(f"Enqueued followup for lead {lead['id']}: job_id={job_id}")
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing followup for lead {lead.get('id')}: {e}")
    except Exception as e:
        logger.error(f"Error in process_outreach_sequences: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass