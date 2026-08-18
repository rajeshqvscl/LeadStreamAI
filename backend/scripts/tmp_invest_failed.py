"""Investigate why fresh leads fail in draft send flow — check FAILED leads and their remarks."""
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

# 1) All FAILED leads with remarks in last 3 days
cur.execute("""
    SELECT lr.id, lr.first_name, lr.last_name, lr.email, lr.user_id,
           lr.email_status, lr.remarks, lr.draft_template_used,
           lr.updated_at::date AS upd,
           lr.is_unsubscribed, lr.email_opt_in,
           EXISTS (SELECT 1 FROM unsubscribe_list ul WHERE LOWER(ul.email) = LOWER(lr.email)) AS in_list
    FROM leads_raw lr
    WHERE lr.email_status = 'FAILED'
      AND lr.updated_at >= NOW() - INTERVAL '5 days'
    ORDER BY lr.updated_at DESC
    LIMIT 60
""")
rows = cur.fetchall()
print(f"=== FAILED leads (last 5 days): {len(rows)} ===")
for r in rows:
    print(f"  id={r['id']} user={r['user_id']} {r['first_name']} {r['last_name']} <{r['email']}> upd={r['upd']} unsub={r['is_unsubscribed']} optin={r['email_opt_in']} in_list={r['in_list']}")
    print(f"      remarks: {(r['remarks'] or '')[:120]}")

# 2) Group by remarks pattern
print()
print("=== Remarks breakdown ===")
cur.execute("""
    SELECT LEFT(COALESCE(remarks, 'NULL'), 80) AS rm, COUNT(*) AS c
    FROM leads_raw
    WHERE email_status = 'FAILED' AND updated_at >= NOW() - INTERVAL '5 days'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 20
""")
for r in cur.fetchall():
    print(f"  [{r['c']:>3}] {r['rm']}")

cur.close()
conn.close()
