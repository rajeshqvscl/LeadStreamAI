"""Check stuck clean leads: any send attempt? Do they match send-approved-batch SELECT?"""
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

# All clean stuck leads (no guards, has draft, PENDING/APPROVED)
cur.execute("""
    SELECT l.id, l.user_id, l.email, l.email_status, l.draft_template_used,
           l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS updated_ist,
           l.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS created_ist
    FROM leads_raw l
    WHERE l.email_status IN ('APPROVED', 'PENDING_APPROVAL')
      AND COALESCE(l.is_responded, FALSE) = FALSE AND l.replied_at IS NULL
      AND COALESCE(l.reply_intent, '') = ''
      AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
      AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
      AND l.email NOT IN (SELECT email FROM unsubscribe_list)
      AND l.email_draft IS NOT NULL
    ORDER BY l.updated_at DESC
""")
leads = cur.fetchall()
print(f"Clean stuck leads: {len(leads)}")
ids = [r['id'] for r in leads]

# Any send ATTEMPT (EMAIL_SENT or EMAIL_SEND_FAILED) activity at all?
cur.execute("""
    SELECT al.lead_id, al.action FROM activity_log al
    WHERE al.lead_id = ANY(%s::int[]) AND al.action IN ('EMAIL_SENT', 'EMAIL_SEND_FAILED')
""", (ids,))
rows = cur.fetchall()
acts = Counter(r['action'] for r in rows)
sent_ever = {r['lead_id'] for r in rows if r['action'] == 'EMAIL_SENT'}
print(f"Ever EMAIL_SENT: {len([r for r in leads if r['id'] in sent_ever])} | "
      f"Ever EMAIL_SEND_FAILED: {acts.get('EMAIL_SEND_FAILED', 0)}")

# Updated today?
today = [r for r in leads if str(r['updated_ist'])[:10] == '2026-08-18']
print(f"Updated today (18 Aug): {len(today)} | older: {len(leads) - len(today)}")

by_user = Counter(r['user_id'] for r in leads)
print(f"By user: {dict(sorted(by_user.items()))}")
by_tpl = Counter(str(r['draft_template_used']) for r in today)
print(f"Today's by template: {dict(sorted(by_tpl.items()))}")

# send-approved-batch SELECT match check (per user, status + guards)
print("\nWould send-approved-batch pick them? (per user, today's only)")
for uid in sorted(by_user):
    t = [r for r in today if r['user_id'] == uid]
    if not t:
        continue
    tids = [r['id'] for r in t]
    cur.execute("""
        SELECT COUNT(*) AS c FROM leads_raw
        WHERE email_status IN ('APPROVED', 'PENDING_APPROVAL')
          AND COALESCE(is_responded, FALSE) = FALSE AND replied_at IS NULL
          AND COALESCE(reply_intent, '') = ''
          AND (email_opt_in IS NULL OR email_opt_in = TRUE)
          AND (is_unsubscribed IS NULL OR is_unsubscribed = FALSE)
          AND email NOT IN (SELECT email FROM unsubscribe_list)
          AND user_id = %s
    """, (uid,))
    print(f"  user {uid}: today's stuck={len(t)}, would-be-picked={cur.fetchone()['c']}")

cur.close()
conn.close()
print("\nDONE")
