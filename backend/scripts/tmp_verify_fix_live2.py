"""Verify the dup-guard fix is live: recent Stage-1 sends going to leads previously blocked by old-campaign entries."""
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

db_url = os.getenv('DATABASE_URL')
db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# Stage-1 sends in the last 90 min — did those leads previously have an OLD Stage-1
# entry (before their last EMAIL_SENT)? That proves the dup-guard fix unblocked them.
cur.execute("""
    SELECT al.lead_id, al.user_id, l.email, l.first_name, l.last_name,
           (al.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') AS sent_ist,
           (SELECT MAX(le.created_at) FROM activity_log le
             WHERE le.lead_id = al.lead_id AND le.action = 'EMAIL_SENT') AS last_email,
           (SELECT MAX(o.created_at) FROM activity_log o
             WHERE o.lead_id = al.lead_id AND o.action = 'AUTO_FOLLOWUP_SENT'
               AND o.details LIKE 'Stage 1%'
               AND o.created_at < (SELECT MAX(le2.created_at) FROM activity_log le2
                                    WHERE le2.lead_id = al.lead_id AND le2.action = 'EMAIL_SENT')) AS old_block_entry
    FROM activity_log al
    JOIN leads_raw l ON l.id = al.lead_id
    WHERE al.action = 'AUTO_FOLLOWUP_SENT' AND al.details LIKE 'Stage 1%'
      AND al.created_at >= NOW() - INTERVAL '90 minutes'
    ORDER BY al.created_at
""")
rows = cur.fetchall()
print(f"Stage-1 AUTO_FOLLOWUP_SENT in last 90 min: {len(rows)}")

prev_blocked = 0
for r in rows:
    if r['old_block_entry']:
        prev_blocked += 1
        name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
        print(f"  ✅ PREV-BLOCKED now sent: {r['sent_ist']} | user={r['user_id']} | {name:<24} {r['email']:<40}")

print(f"\nPreviously-dup-guard-blocked leads that NOW got their Stage-1: {prev_blocked} / {len(rows)}")

# Also: current queue health — how many stage-0 leads still due + how many old-blocked remain
cur.execute("""
    WITH queue AS (
        SELECT DISTINCT ON (l.user_id, LOWER(l.email)) l.id, l.user_id
        FROM leads_raw l
        JOIN users u ON l.user_id = u.id
        WHERE l.followup_status = 'ACTIVE'
        AND l.email_status IN ('SENT', 'OPENED', 'CLICKED')
        AND COALESCE(l.is_responded, FALSE) = FALSE
        AND l.replied_at IS NULL
        AND COALESCE(l.reply_intent, '') NOT IN ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED', 'NEEDS_MORE_INFO')
        AND l.followup_stage = 0
        AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
        AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
        AND l.email NOT IN (SELECT email FROM unsubscribe_list)
        ORDER BY l.user_id, LOWER(l.email), l.last_outreach_at ASC
    )
    SELECT COUNT(*) AS total FROM queue
""")
print(f"\nStage-0 leads remaining in queue: {cur.fetchone()['total']}")

cur.close()
conn.close()
print("\nDONE")
