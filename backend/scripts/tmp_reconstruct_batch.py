"""Reconstruct user 4's today draft→send batches — find leads drafted but never sent."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
for env_loc in ['app/.env', 'backend/app/.env', '../backend/app/.env', '../../backend/app/.env']:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

from app.database import get_db_connection
from psycopg2.extras import DictCursor

conn = get_db_connection()
cur = conn.cursor(cursor_factory=DictCursor)

# User 4: leads with DRAFT_GENERATED activity in the last 24h, grouped by hour of draft
cur.execute("""
    SELECT date_trunc('hour', a.created_at) AS draft_hr, COUNT(DISTINCT a.lead_id) AS drafted,
           COUNT(DISTINCT a.lead_id) FILTER (WHERE lr.email_status = 'SENT') AS sent,
           COUNT(DISTINCT a.lead_id) FILTER (WHERE lr.email_status = 'PENDING_APPROVAL') AS pending,
           COUNT(DISTINCT a.lead_id) FILTER (WHERE lr.email_status = 'OPENED') AS opened,
           COUNT(DISTINCT a.lead_id) FILTER (WHERE lr.email_status = 'CLICKED') AS clicked
    FROM activity_log a
    JOIN leads_raw lr ON lr.id = a.lead_id
    WHERE a.action = 'DRAFT_GENERATED' AND a.created_at >= NOW() - INTERVAL '1 day'
      AND lr.user_id = 4
    GROUP BY 1 ORDER BY 1
""")
print("=== User 4: drafts per hour -> outcome ===")
for r in cur.fetchall():
    print(f"  {r['draft_hr']} | drafted={r['drafted']} sent={r['sent']} pending={r['pending']} opened={r['opened']} clicked={r['clicked']}")

# The most recent draft batch: which leads are STILL pending (never attempted)?
print()
print("=== User 4: STILL-PENDING leads drafted today (never sent) — full list ===")
cur.execute("""
    SELECT lr.id, lr.first_name, lr.last_name, lr.email, lr.draft_template_used, lr.updated_at,
           (SELECT a.created_at FROM activity_log a WHERE a.lead_id = lr.id
             AND a.action IN ('EMAIL_SENT','EMAIL_SEND_FAILED','DRAFT_GENERATED')
             ORDER BY a.created_at DESC LIMIT 1) AS last_activity,
           (SELECT a.action FROM activity_log a WHERE a.lead_id = lr.id
             AND a.action IN ('EMAIL_SENT','EMAIL_SEND_FAILED','DRAFT_GENERATED')
             ORDER BY a.created_at DESC LIMIT 1) AS last_action
    FROM leads_raw lr
    WHERE lr.user_id = 4 AND lr.email_status = 'PENDING_APPROVAL'
      AND lr.updated_at >= NOW() - INTERVAL '1 day'
      AND NOT (lr.is_unsubscribed OR lr.email_opt_in = FALSE
               OR EXISTS (SELECT 1 FROM unsubscribe_list ul WHERE LOWER(ul.email) = LOWER(lr.email)))
    ORDER BY lr.updated_at DESC
    LIMIT 40
""")
rows = cur.fetchall()
print(f"  (showing {len(rows)})")
for r in rows:
    print(f"  id={r['id']} {r['first_name']} {r['last_name']} <{(r['email'] or '')[:45]}> tpl={r['draft_template_used']}")
    print(f"      updated={r['updated_at']} | last={r['last_action']} @ {r['last_activity']}")

cur.close()
conn.close()
