import contextlib
import logging
import re

import psycopg2.extras
from app.api.drafts import get_followup_signature_markdown
from app.core.followup.engine import get_followup_engine
from app.core.pipeline.claims import LeadClaimer
from app.database import get_db_connection
from app.email_engine.producer import get_email_producer

logger = logging.getLogger(__name__)


def is_generic_followup(body: str | None) -> bool:
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
    return "just following up on the climate agritech platform opportunity shared earlier" in cleaned


def get_template_followup(lead: dict, stage: int) -> str:
    """Return a follow-up email BODY (markdown string) for the given lead + stage.

    Reuses the same campaign/template resolution as FollowUpEngine so the body
    matches what the engine would send. Falls back to a generic follow-up string
    if resolution fails for any reason.
    """
    from app.core.followup.campaign_resolver import CampaignResolver, LeadData

    lead_data = LeadData(
        id=lead.get("id", 0),
        draft_template_used=lead.get("draft_template_used", "") or "",
        original_subject=lead.get("last_outreach_subject", "") or lead.get("first_outreach_subject", "") or "",
        email_draft=lead.get("email_draft", "") or "",
        persona=lead.get("persona", "") or "",
        sector=lead.get("sector", "") or "",
        sender_name=lead.get("sender_name", "") or lead.get("full_name", "") or "",
        sender_email=lead.get("sender_email", "") or "",
        lead_type=lead.get("lead_type", "INVESTOR") or "INVESTOR",
    )
    try:
        campaign = CampaignResolver.resolve(lead_data)
        template = CampaignResolver.get_template(campaign, stage)
        name = (lead.get("first_name") or "").strip() or "there"
        return template.format(name=name)
    except Exception as e:
        logger.warning(f"get_template_followup falling back to generic template: {e}")
        return "Hi {name},\n\nJust following up on my previous email. Let me know if you have any questions!\n\nBest regards,".format(
            name=(lead.get("first_name") or "there")
        )


def process_outreach_sequences():
    """
    Background worker that identifies leads due for follow-ups.
    Uses FollowUpEngine for evaluation and EmailProducer for queueing.
    """
    from app.core.pipeline.scheduler import get_scheduler_config

    config = get_scheduler_config()
    engine = get_followup_engine()
    producer = get_email_producer()

    if not config.is_followup_working_hours_now():
        logger.info("Outreach paused: Outside followup working hours (8:30AM-8PM)")
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
            from app.core.config import get_followup_settings
            max_per_cycle = get_followup_settings().max_auto_sends_per_cycle

            for lead in group:
                if sent_count >= max_per_cycle:
                    logger.info(f"Per-cycle cap ({max_per_cycle}) reached for user {uid} — remaining leads picked up next cycle.")
                    break

                # Only skip terminal pipeline states (must match LeadState enum values)
                TERMINAL = {'CLOSED_WON', 'CLOSED_LOST', 'UNSUBSCRIBED', 'BOUNCED'}
                if lead.get('pipeline_state') in TERMINAL:
                    continue

                try:
                    # Evaluate if lead is due for follow-up
                    action = engine.evaluate(lead)

                    if not action.should_send:
                        continue

                    # BUG 2: atomically claim the lead before enqueueing so the
                    # stage advances exactly once (prevents duplicate sends).
                    current_stage = lead.get('followup_stage', 0) or 0
                    next_stage = action.stage
                    claimed = LeadClaimer.claim_for_followup(
                        lead['id'],
                        expected_stage=current_stage,
                        new_stage=next_stage,
                        subject=action.subject,
                        new_status='COMPLETED' if next_stage >= action.max_stage else 'ACTIVE',
                    )
                    if not claimed:
                        logger.info(f"Lead {lead['id']} already advanced by another worker; skipping")
                        continue

                    # Build email content with signature
                    followup_sig = get_followup_signature_markdown(str(uid))
                    body_with_sig = action.body
                    if followup_sig:
                        body_with_sig = body_with_sig.rstrip() + f"\n\n{followup_sig}"

                    # Convert to HTML
                    from app.api.drafts import markdown_to_html
                    from app.services.email_service import (
                        get_user_image_height,
                        get_user_image_width,
                    )
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
                    logger.exception(f"Error processing followup for lead {lead.get('id')}: {e}")
    except Exception as e:
        logger.exception(f"Error in process_outreach_sequences: {e}")
    finally:
        with contextlib.suppress(Exception):
            conn.close()
