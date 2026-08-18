"""Deep dive: today's stuck Labbuddy leads (user 4) — full activity + send attempt history."""
import sys
import os
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env", "../../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

import psycopg2
from psycopg2.extras import RealDictCursor
from collections import Counter

db_url = os.getenv('DATABASE_URL')
db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# Today's stuck leads for user 4
cur.execute("""
    SELECT l.id, l.email, l.email_status, l.draft_template_used,
           l.gmail_thread_id IS NOT NULL AS has_thread,
           l.gmail_message_id IS NOT NULL AS has_msg,
           l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS updated_ist
    FROM leads_raw l
    WHERE l.email_status IN ('APPROVED', 'PENDING_APPROVAL')
      AND l.user_id = 4
      AND COALESCE(l.is_responded, FALSE) = FALSE AND l.replied_at IS NULL
      AND COALESCE(l.reply_intent, '') = ''
      AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
      AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
      AND l.email NOT IN (SELECT email FROM unsubscribe_list)
      AND l.email_draft IS NOT NULL
      AND l.updated_at >= '2026-08-18 00:00:00+05:30'
    ORDER BY l.updated_at DESC
""")
leads = cur.fetchall()
print(f"Today's stuck leads (user 4): {len(leads)}")
ids = [r['id'] for r in leads]

# Full activity for these leads — what happened?
cur.execute("""
    SELECT al.lead_id, al.action, COUNT(*) AS c,
           MAX(al.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') AS last_ist
    FROM activity_log al WHERE al.lead_id = ANY(%s::int[])
    GROUP BY al.lead_id, al.action ORDER BY al.lead_id, al.action
""", (ids,))
acts = {}
for r in cur.fetchall():
    acts.setdefault(r['lead_id'], []).append((r['action'], r['c'], r['last_ist']))

# Distribution of last activity per lead
last_action = Counter()
for r in leads:
    a = acts.get(r['id'], [])
    if a:
        last_action[a[-1][0]] += 1
    else:
        last_action['(no activity)'] += 1
print(f"\nLast activity per lead: {dict(last_action)}")

# Leads with any EMAIL_SENT today
cur.execute("""
    SELECT al.lead_id FROM activity_log al
    WHERE al.lead_id = ANY(%s::int[]) AND al.action = 'EMAIL_SENT'
      AND al.created_at >= '2026-08-18 00:00:00+00'
""", (ids,))
sent_today = {r['lead_id'] for r in cur.fetchall()}
print(f"Sent today but status still PENDING/APPROVED: {len(sent_today)}")

# Leads with DRAFT_GENERATED today (drafted today)
cur.execute("""
    SELECT al.lead_id FROM activity_log al
    WHERE al.lead_id = ANY(%s::int[]) AND al.action = 'DRAFT_GENERATED'
      AND al.created_at >= '2026-08-18 00:00:00+00'
""", (ids,))
drafted_today = {r['lead_id'] for r in cur.fetchall()}
print(f"Drafted today (DRAFT_GENERATED): {len(drafted_today)}")
print(f"  of which SENT today too: {len(sent_today & drafted_today)}")
print(f"  drafted today, never sent: {len(drafted_today - sent_today)}")

# Show a couple full timelines
print("\n=== Sample timelines ===")
shown = 0
for r in leads:
    a = acts.get(r['id'], [])
    if a and a[-1][0] == 'DRAFT_GENERATED' and r['id'] not in sent_today and shown < 3:
        cur.execute("""
            SELECT action, details, (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') AS ts
            FROM activity_log WHERE lead_id = %s ORDER BY created_at DESC LIMIT 5
        """, (r['id'],))
        print(f"\n  id={r['id']} {r['email']} status={r['email_status']} thread={r['has_thread']} msg={r['has_msg']}")
        for x in cur.fetchall():
            print(f"    {x['ts']} | {x['action']} | {str(x['details'] or '')[:60]}")
        shown += 1

cur.close()
conn.close()
print("\nDONE")
