#!/usr/bin/env python3
"""
Schedule all previously due leads:
1. Ensure all are ACTIVE, email_status=SENT
2. Verify no replied/not-interested
3. Get lead IDs for bulk approve
"""
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

# Find ALL leads that need followup (due before OR on today)
cur.execute("""
    SELECT 
        l.id,
        COALESCE(l.first_name || ' ' || l.last_name, l.email) AS name,
        l.user_id,
        l.followup_stage,
        l.followup_status,
        l.lead_type,
        l.email_status,
        l.reply_intent,
        l.is_responded,
        l.last_outreach_at,
        CASE 
            WHEN COALESCE(l.followup_stage, 0) = 0 THEN 2
            WHEN COALESCE(l.followup_stage, 0) = 1 AND LOWER(COALESCE(l.lead_type, '')) = 'client' THEN 4
            WHEN COALESCE(l.followup_stage, 0) = 1 THEN 5
            WHEN COALESCE(l.followup_stage, 0) = 2 THEN 7
            ELSE 999
        END AS interval_days
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
all_leads = cur.fetchall()

# Filter: due (last_outreach + interval <= NOW)
due_leads = []
for lead in all_leads:
    if lead['last_outreach_at'] and lead['interval_days'] < 999:
        due_at = lead['last_outreach_at'] + datetime.timedelta(days=lead['interval_days'])
        if due_at <= now:
            due_leads.append(lead)

print(f"Total active: {len(all_leads)}")
print(f"Currently due: {len(due_leads)}")
print()

# Group by user
from collections import defaultdict
by_user = defaultdict(list)
for lead in due_leads:
    by_user[lead['user_id']].append(lead)

cur.execute("SELECT id, username FROM users")
user_map = {r['id']: r['username'] for r in cur.fetchall()}

print("=== DUE LEADS BY USER ===")
total_scheduled = 0
for uid, leads in sorted(by_user.items()):
    uname = user_map.get(uid, f"unknown({uid})")
    print(f"  {uname} (user_id={uid}): {len(leads)} leads")
    total_scheduled += len(leads)

print(f"\nTotal to schedule: {total_scheduled}")

# Save all due lead IDs grouped by user for bulk approve
all_due_ids = [l['id'] for l in due_leads]
print(f"All due lead IDs count: {len(all_due_ids)}")

cur.close()
conn.close()
