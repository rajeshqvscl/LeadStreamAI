"""Investigate stuck PENDING_APPROVAL leads — are they fresh, and did any send attempt happen?"""
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

# User 4 stuck leads — breakdown by unsubscribed vs clean
cur.execute("""
    SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE lr.is_unsubscribed OR lr.email_opt_in = FALSE
                         OR EXISTS (SELECT 1 FROM unsubscribe_list ul WHERE LOWER(ul.email) = LOWER(lr.email))) AS unsubscribed,
        COUNT(*) FILTER (WHERE NOT (lr.is_unsubscribed OR lr.email_opt_in = FALSE
                         OR EXISTS (SELECT 1 FROM unsubscribe_list ul WHERE LOWER(ul.email) = LOWER(lr.email)))) AS clean
    FROM leads_raw lr
    WHERE lr.user_id = 4 AND lr.email_status = 'PENDING_APPROVAL'
      AND lr.updated_at >= NOW() - INTERVAL '1 day'
""")
r = cur.fetchone()
print(f"User 4 stuck today: total={r['total']} | unsubscribed={r['unsubscribed']} | CLEAN/fresh={r['clean']}")

# Sample clean stuck leads with their latest activity
cur.execute("""
    SELECT lr.id, lr.first_name, lr.last_name, lr.email, lr.draft_template_used,
           lr.updated_at, lr.created_at, lr.last_outreach_at,
           (SELECT action FROM activity_log a WHERE a.lead_id = lr.id ORDER BY a.created_at DESC LIMIT 1) AS last_action,
           (SELECT created_at FROM activity_log a WHERE a.lead_id = lr.id ORDER BY a.created_at DESC LIMIT 1) AS last_activity_at
    FROM leads_raw lr
    WHERE lr.user_id = 4 AND lr.email_status = 'PENDING_APPROVAL'
      AND lr.updated_at >= NOW() - INTERVAL '1 day'
      AND NOT (lr.is_unsubscribed OR lr.email_opt_in = FALSE
               OR EXISTS (SELECT 1 FROM unsubscribe_list ul WHERE LOWER(ul.email) = LOWER(lr.email)))
    ORDER BY lr.updated_at DESC
    LIMIT 12
""")
print()
print("=== CLEAN stuck leads (fresh) — sample ===")
for row in cur.fetchall():
    print(f"  id={row['id']} {row['first_name']} {row['last_name']} <{row['email']}> tpl={row['draft_template_used']}")
    print(f"      upd={row['updated_at']} last_act={row['last_action']} @ {row['last_activity_at']}")

# Check: do these clean leads have ANY activity after their draft was generated?
cur.execute("""
    SELECT lr.id,
           (SELECT COUNT(*) FROM activity_log a WHERE a.lead_id = lr.id AND a.action IN ('EMAIL_SENT','EMAIL_SEND_FAILED')) AS send_attempts
    FROM leads_raw lr
    WHERE lr.user_id = 4 AND lr.email_status = 'PENDING_APPROVAL'
      AND lr.updated_at >= NOW() - INTERVAL '1 day'
      AND NOT (lr.is_unsubscribed OR lr.email_opt_in = FALSE
               OR EXISTS (SELECT 1 FROM unsubscribe_list ul WHERE LOWER(ul.email) = LOWER(lr.email)))
""")
rows = cur.fetchall()
with_attempts = [r for r in rows if r['send_attempts'] > 0]
print(f"\nCLEAN stuck leads: {len(rows)} total, {len(with_attempts)} had send attempts (EMAIL_SENT/FAILED logged), {len(rows)-len(with_attempts)} NEVER attempted")

cur.close()
conn.close()
