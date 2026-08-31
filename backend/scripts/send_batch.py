#!/usr/bin/env python3
"""Send followups in a batch of 50 leads."""
import os, sys, datetime, logging, time
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv('.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

from database import get_db_connection
from core.followup.engine import get_followup_engine
from core.pipeline.claims import LeadClaimer
from email_engine.producer import get_email_producer
from api.drafts import markdown_to_html, get_followup_signature_markdown
from services.email_service import get_user_image_width, get_user_image_height

import psycopg2.extras

engine = get_followup_engine()
producer = get_email_producer()

# Check working hours
if not engine.scheduler_config.is_followup_working_hours_now():
    print("Outside followup working hours. Aborting.")
    sys.exit(0)

conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

BATCH_SIZE = 50

cur.execute("""
    SELECT l.*, u.id as sender_id, u.email as sender_email, u.full_name as sender_name,
           u.auto_followup, u.google_refresh_token,
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
      AND u.auto_followup = TRUE
      AND u.google_refresh_token IS NOT NULL
    ORDER BY l.last_outreach_at ASC
    LIMIT %s
""", (BATCH_SIZE,))
leads = cur.fetchall()
cur.close()
conn.close()

print(f"Batch: {len(leads)} leads to process")

sent = 0
skipped = 0
errors = 0

for lead in leads:
    lead = dict(lead)
    try:
        action = engine.evaluate(lead)
        if not action.should_send:
            skipped += 1
            continue

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
            skipped += 1
            continue

        followup_sig = get_followup_signature_markdown(str(lead['sender_id']))
        body_with_sig = action.body
        if followup_sig:
            body_with_sig = body_with_sig.rstrip() + f"\n\n{followup_sig}"

        email_font = lead.get('email_font') or 'sans-serif'
        email_font_size = lead.get('email_font_size') or '15px'
        html_content = markdown_to_html(body_with_sig, font_family=email_font, font_size=email_font_size, image_width=get_user_image_width(lead['sender_id']), image_height=get_user_image_height(lead['sender_id']))

        job_id = producer.send_followup(
            lead_id=lead['id'],
            stage=action.stage,
            user_id=lead['sender_id'],
            to_email=lead['email'],
            subject=action.subject,
            html_content=html_content,
            from_email=lead['sender_email'],
            from_name=lead['sender_name'],
            thread_id=lead.get('gmail_thread_id'),
            in_reply_to=lead.get('gmail_message_id'),
            template_name=action.campaign,
        )
        sent += 1
        print(f"  [{sent}] {lead.get('first_name','')} {lead.get('last_name','')} ({lead['email']}) -> stage {next_stage}")

    except Exception as e:
        errors += 1
        print(f"  ERR lead {lead['id']}: {e}")

print(f"\nSENT: {sent}, SKIPPED: {skipped}, ERRORS: {errors}")
