"""Analyze today's draft→send pattern — find leads that got drafted today but never sent."""
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

# Leads that had DRAFT_GENERATED activity today (user 4) — what happened after?
cur.execute("""
    SELECT lr.id, lr.email, lr.email_status, lr.draft_template_used,
           lr.is_unsubscribed, lr.email_opt_in,
           EXISTS (SELECT 1 FROM unsubscribe_list ul WHERE LOWER(ul.email) = LOWER(lr.email)) AS in_list,
           (SELECT COUNT(*) FROM activity_log a WHERE a.lead_id = lr.id
             AND a.action IN ('EMAIL_SENT','EMAIL_SEND_FAILED')
             AND a.created_at > (SELECT MAX(created_at) FROM activity_log a2
                                  WHERE a2.lead_id = lr.id AND a2.action = 'DRAFT_GENERATED')) AS attempts_after_draft
    FROM leads_raw lr
    WHERE EXISTS (SELECT 1 FROM activity_log a WHERE a.lead_id = lr.id
                  AND a.action = 'DRAFT_GENERATED' AND a.created_at >= NOW() - INTERVAL '1 day')
      AND lr.user_id = 4
    ORDER BY lr.id
""")
rows = cur.fetchall()
from collections import Counter
status_ct = Counter(r['email_status'] for r in rows)
print(f"User 4 leads drafted today: {len(rows)}")
print(f"  by status: {dict(status_ct)}")

drafted_not_sent = [r for r in rows if r['email_status'] not in ('SENT',)]
print(f"\nDrafted today, NOT sent ({len(drafted_not_sent)}):")
for r in drafted_not_sent[:15]:
    print(f"  id={r['id']} {r['email']:<45} status={r['email_status']:<16} unsub={r['is_unsubscribed']} optin={r['email_opt_in']} in_list={r['in_list']} attempts_after={r['attempts_after_draft']}")

cur.close()
conn.close()
