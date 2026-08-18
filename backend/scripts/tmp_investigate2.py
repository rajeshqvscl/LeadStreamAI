"""Check: were the stuck PENDING_APPROVAL leads sent before and re-drafted? And daily-limit checks."""
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

# 1) For a sample of the 121 "sent but re-drafted" leads: activity timeline
cur.execute("""
    SELECT l.id, l.email, l.email_status, l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS upd_ist
    FROM leads_raw l
    WHERE l.email_status IN ('APPROVED', 'PENDING_APPROVAL')
      AND COALESCE(l.is_responded, FALSE) = FALSE AND l.replied_at IS NULL
      AND COALESCE(l.reply_intent, '') = ''
      AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
      AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
      AND l.email NOT IN (SELECT email FROM unsubscribe_list)
      AND l.email_draft IS NOT NULL
      AND EXISTS(SELECT 1 FROM activity_log al WHERE al.lead_id = l.id AND al.action = 'EMAIL_SENT')
    LIMIT 8
""")
sample = cur.fetchall()
print(f"Sample of sent-but-PENDING leads: {len(sample)}")
for r in sample:
    cur.execute("""
        SELECT action, details, (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') AS ts
        FROM activity_log WHERE lead_id = %s ORDER BY created_at DESC LIMIT 6
    """, (r['id'],))
    print(f"\n  id={r['id']} {r['email']} status={r['email_status']} updated={r['upd_ist']}")
    for a in cur.fetchall():
        print(f"    {a['ts']} | {a['action']} | {str(a['details'] or '')[:70]}")

# 2) Draft regenerate frequency: DRAFT_GENERATED after last EMAIL_SENT
cur.execute("""
    SELECT COUNT(*) AS c FROM activity_log al
    WHERE al.action = 'DRAFT_GENERATED'
      AND al.created_at > (SELECT COALESCE(MAX(le.created_at), '1970-01-01') FROM activity_log le
                           WHERE le.lead_id = al.lead_id AND le.action = 'EMAIL_SENT')
""")
print(f"\nDRAFT_GENERATED events AFTER last EMAIL_SENT (same lead): {cur.fetchone()['c']}")

# 3) Daily limit check function
cur.execute("SELECT id, full_name, outreach_daily_limit FROM users WHERE id IN (1,2,4,5,9,16) ORDER BY id")
print("\nUser daily limits:")
for r in cur.fetchall():
    print(f"  {r['id']}: {r['full_name']} -> {r['outreach_daily_limit']}")

# 4) How many FAILED leads exist (send attempted but failed)?
cur.execute("""
    SELECT user_id, COUNT(*) FROM leads_raw WHERE email_status = 'FAILED' GROUP BY user_id ORDER BY user_id
""")
print("\nFAILED leads by user:")
for r in cur.fetchall():
    print(f"  user {r['user_id']}: {r['count']}")

cur.close()
conn.close()
print("\nDONE")
