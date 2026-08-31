#!/usr/bin/env python3
"""
Schedule all previously due + today's due followups for immediate sending.
Runs the followup engine directly, claims leads, and enqueues emails.
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

logger.info(f"Starting schedule at {now} IST")

conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# Step 1: Query ALL eligible leads
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
      AND u.google_refresh_token IS NOT NULL
    ORDER BY l.user_id, LOWER(l.email), l.last_outreach_at ASC
""")
leads = cur.fetchall()
cur.close()
conn.close()

logger.info(f"Total eligible leads: {len(leads)}")

# Step 2: Group by user
from collections import defaultdict
user_leads = defaultdict(list)
for lead in leads:
    user_leads[lead['sender_id']].append(dict(lead))

# Step 3: Process each user
total_sent = 0
total_skipped = 0
total_errors = 0
user_stats = {}

from core.config import get_followup_settings
settings = get_followup_settings()

for uid, group in user_leads.items():
    first_lead = group[0]
    uname = first_lead['sender_name'] or first_lead['sender_email']
    logger.info(f"Processing user {uid} ({uname}): {len(group)} leads, auto_followup={first_lead['auto_followup']}, has_token={bool(first_lead['google_refresh_token'])}")
    
    if not first_lead['auto_followup'] or not first_lead['google_refresh_token']:
        logger.info(f"  Skipping user {uid}: auto_followup=False or no token")
        total_skipped += len(group)
        user_stats[uname] = {'eligible': len(group), 'sent': 0, 'skipped': len(group), 'errors': 0}
        continue
    
    sent_count = 0
    error_count = 0
    skip_count = 0
    
    TERMINAL = {'CLOSED_WON', 'CLOSED_LOST', 'UNSUBSCRIBED', 'BOUNCED'}
    
    for lead in group:
        if sent_count >= settings.max_auto_sends_per_cycle:
            logger.info(f"  Per-cycle cap ({settings.max_auto_sends_per_cycle}) reached for user {uid}")
            break
        
        if lead.get('pipeline_state') in TERMINAL:
            skip_count += 1
            continue
        
        try:
            # Evaluate
            action = engine.evaluate(lead)
            if not action.should_send:
                skip_count += 1
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
                skip_count += 1
                continue
            
            # Build email
            followup_sig = get_followup_signature_markdown(str(uid))
            body_with_sig = action.body
            if followup_sig:
                body_with_sig = body_with_sig.rstrip() + f"\n\n{followup_sig}"
            
            email_font = lead.get('email_font') or 'sans-serif'
            email_font_size = lead.get('email_font_size') or '15px'
            image_width = get_user_image_width(uid)
            image_height = get_user_image_height(uid)
            html_content = markdown_to_html(body_with_sig, font_family=email_font, font_size=email_font_size, image_width=image_width, image_height=image_height)
            
            # Enqueue
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
            
            sent_count += 1
            logger.info(f"  Enqueued: {lead.get('first_name', '')} {lead.get('last_name', '')} ({lead['email']}) -> stage {next_stage}, job={job_id}")
        
        except Exception as e:
            error_count += 1
            logger.error(f"  Error for lead {lead['id']}: {e}")
    
    user_stats[uname] = {'eligible': len(group), 'sent': sent_count, 'skipped': skip_count, 'errors': error_count}
    total_sent += sent_count
    total_skipped += skip_count
    total_errors += error_count

# Summary
print("\n" + "=" * 70)
print("SCHEDULE SUMMARY")
print("=" * 70)
for uname, stats in user_stats.items():
    print(f"  {uname}: eligible={stats['eligible']}, sent={stats['sent']}, skipped={stats['skipped']}, errors={stats['errors']}")
print("-" * 70)
print(f"  TOTAL: eligible={len(leads)}, sent={total_sent}, skipped={total_skipped}, errors={total_errors}")
print("=" * 70)
