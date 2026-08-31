#!/usr/bin/env python3
"""Find all previously due leads and schedule them for 3:15 PM IST."""
import os, sys, datetime
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv('.env')
from database import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now = datetime.datetime.now(tz)
today_date = now.date()
print(f"Now IST: {now}")
print(f"Today: {today_date}")
print()

# Step 1: Find all previously due leads
cur.execute("""
    SELECT 
        l.id,
        COALESCE(l.first_name || ' ' || l.last_name, l.email) AS name,
        l.email, l.user_id, l.followup_stage, l.followup_status,
        l.lead_type, l.email_status, l.reply_intent, l.is_responded,
        l.last_outreach_at, l.first_outreach_at,
        l.last_outreach_subject, l.first_outreach_subject,
        l.draft_template_used, l.gmail_thread_id, l.gmail_message_id,
        CASE 
            WHEN COALESCE(l.followup_stage, 0) = 0 THEN l.last_outreach_at + INTERVAL '2 days'
            WHEN COALESCE(l.followup_stage, 0) = 1 AND LOWER(COALESCE(l.lead_type, '')) = 'client' THEN l.last_outreach_at + INTERVAL '4 days'
            WHEN COALESCE(l.followup_stage, 0) = 1 THEN l.last_outreach_at + INTERVAL '5 days'
            WHEN COALESCE(l.followup_stage, 0) = 2 THEN l.last_outreach_at + INTERVAL '7 days'
            ELSE l.last_outreach_at + INTERVAL '999 days'
        END AS due_at
    FROM leads_raw l
    WHERE l.followup_status = 'ACTIVE'
      AND COALESCE(l.is_responded, FALSE) = FALSE
      AND COALESCE(l.reply_intent, '') NOT IN ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED', 'NEEDS_MORE_INFO')
      AND l.email_status IN ('SENT', 'OPENED', 'CLICKED')
      AND l.followup_stage < 3
      AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
      AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
      AND l.last_outreach_at IS NOT NULL
    ORDER BY l.user_id, l.last_outreach_at ASC
""")
all_active = cur.fetchall()

# Filter: due BEFORE today
previously_due = []
today_due = []
for lead in all_active:
    due_at = lead['due_at']
    if due_at and due_at.date() < today_date:
        previously_due.append(lead)
    elif due_at and due_at.date() == today_date:
        today_due.append(lead)

print(f"Total active followup leads: {len(all_active)}")
print(f"Previously due (before today): {len(previously_due)}")
print(f"Due today: {len(today_due)}")
print()

# Safety check: exclude any replied/not_interested
safe_previously_due = []
excluded = 0
for lead in previously_due:
    intent = (lead['reply_intent'] or '').upper()
    if intent in ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED', 'NEEDS_MORE_INFO'):
        excluded += 1
        continue
    if lead['is_responded']:
        excluded += 1
        continue
    safe_previously_due.append(lead)

print(f"After safety filter (excluded {excluded} replied/not-interested): {len(safe_previously_due)}")
print()

# Group by user
from collections import defaultdict
by_user = defaultdict(list)
for lead in safe_previously_due:
    by_user[lead['user_id']].append(lead)

cur.execute("SELECT id, username FROM users")
user_map = {r['id']: r['username'] for r in cur.fetchall()}

print("=== PREVIOUSLY DUE LEADS BY USER ===")
for uid, leads in sorted(by_user.items()):
    uname = user_map.get(uid, f"unknown({uid})")
    print(f"  {uname} (user_id={uid}): {len(leads)} leads")
    for l in leads[:3]:
        print(f"    - {l['name'][:35]} | stage={l['followup_stage']} | type={l['lead_type']} | due={l['due_at']}")
    if len(leads) > 3:
        print(f"    ... and {len(leads) - 3} more")

# Save lead IDs for scheduling
lead_ids = [l['id'] for l in safe_previously_due]
print(f"\nTotal leads to schedule: {len(lead_ids)}")
print(f"Lead IDs (first 20): {lead_ids[:20]}")

cur.close()
conn.close()
