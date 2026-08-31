#!/usr/bin/env python3
"""
Schedule leads whose last_outreach was Aug 24, 25, 26, 27
into 3 batches: 4:00 PM, 4:15 PM, 4:30 PM IST today.
"""
import os, sys, datetime, logging
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
from services.email_service import get_user_email_font, get_user_email_font_size, get_user_image_width, get_user_image_height

import psycopg2.extras

engine = get_followup_engine()
producer = get_email_producer()

tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now = datetime.datetime.now(tz)
today_date = now.date()

logger.info(f"Running at {now} IST — today is {today_date}")

# ── Batch schedule times (IST today) ──
BATCH_TIMES = [
    today_date.replace(hour=16, minute=0, second=0, microsecond=0),   # 4:00 PM
    today_date.replace(hour=16, minute=15, second=0, microsecond=0),  # 4:15 PM
    today_date.replace(hour=16, minute=30, second=0, microsecond=0),  # 4:30 PM
]

# ── Step 1: Fetch eligible leads with last_outreach Aug 24-27 ──
conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

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
      AND u.google_refresh_token IS NOT NULL
      AND u.auto_followup = TRUE
      AND (l.last_outreach_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date
          IN ('2026-08-24'::date, '2026-08-25'::date, '2026-08-26'::date, '2026-08-27'::date)
    ORDER BY l.last_outreach_at ASC
""")
leads = cur.fetchall()
cur.close()
conn.close()

total = len(leads)
logger.info(f"Found {total} eligible leads (last_outreach Aug 24-27)")

if total == 0:
    print("No eligible leads found. Exiting.")
    sys.exit(0)

# ── Step 2: Split into 3 roughly equal batches ──
batch_size = (total + 2) // 3  # ceiling division
batches = [
    leads[i * batch_size : (i + 1) * batch_size]
    for i in range(3)
]
# Ensure we only use the filled batches
batches = [b for b in batches if b]

# ── Step 3: Schedule each batch ──
from collections import defaultdict
total_scheduled = 0
total_skipped = 0
total_errors = 0

for batch_idx, (batch_leads, scheduled_at) in enumerate(zip(batches, BATCH_TIMES)):
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH {batch_idx + 1}: {len(batch_leads)} leads → scheduled for {scheduled_at.strftime('%I:%M %p IST')}")
    logger.info(f"{'='*60}")

    sent = 0
    skipped = 0
    errors = 0

    for lead in batch_leads:
        lead = dict(lead)
        try:
            # Evaluate followup
            action = engine.evaluate(lead)
            if not action.should_send:
                skipped += 1
                continue

            # Claim
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

            # Build email HTML
            followup_sig = get_followup_signature_markdown(str(lead['sender_id']))
            body_with_sig = action.body
            if followup_sig:
                body_with_sig = body_with_sig.rstrip() + f"\n\n{followup_sig}"

            email_font = lead.get('email_font') or 'sans-serif'
            email_font_size = lead.get('email_font_size') or '15px'
            image_width = get_user_image_width(lead['sender_id'])
            image_height = get_user_image_height(lead['sender_id'])
            html_content = markdown_to_html(
                body_with_sig,
                font_family=email_font,
                font_size=email_font_size,
                image_width=image_width,
                image_height=image_height,
            )

            # Enqueue for scheduled delivery
            job_id = producer.send_scheduled(
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
                scheduled_at=scheduled_at,
            )

            sent += 1
            logger.info(
                f"  ✓ [{sent}] {lead.get('first_name', '')} {lead.get('last_name', '')} "
                f"({lead['email']}) → stage {next_stage}, scheduled {scheduled_at.strftime('%I:%M %p')}"
            )

        except Exception as e:
            errors += 1
            logger.error(f"  ✗ Error for lead {lead.get('id')}: {e}")

    total_scheduled += sent
    total_skipped += skipped
    total_errors += errors
    logger.info(f"Batch {batch_idx + 1} done: scheduled={sent}, skipped={skipped}, errors={errors}")

# ── Summary ──
print("\n" + "=" * 60)
print("SCHEDULE SUMMARY — Aug 24-27 Leads → Today's Batches")
print("=" * 60)
for i, (batch_leads, st) in enumerate(zip(batches, BATCH_TIMES)):
    print(f"  Batch {i+1} ({st.strftime('%I:%M %p IST')}): {len(batch_leads)} leads")
print("-" * 60)
print(f"  TOTAL: eligible={total}, scheduled={total_scheduled}, skipped={total_skipped}, errors={total_errors}")
print("=" * 60)
