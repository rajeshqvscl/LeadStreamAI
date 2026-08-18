"""Find the discriminator: same draft batch, some SENT some PENDING — compare fields."""
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

# Leads drafted today 09:00-09:05 for user 4 (vertexventures batch) — outcome comparison
cur.execute("""
    SELECT lr.id, lr.email, lr.email_status, lr.user_id,
           lr.gmail_draft_id IS NOT NULL AS has_gmail_draft,
           lr.draft_template_used, lr.last_outreach_at, lr.followup_status, lr.followup_stage,
           (SELECT a.created_at FROM activity_log a WHERE a.lead_id = lr.id AND a.action = 'DRAFT_GENERATED'
             ORDER BY a.created_at DESC LIMIT 1) AS drafted_at,
           (SELECT a.created_at FROM activity_log a WHERE a.lead_id = lr.id AND a.action IN ('EMAIL_SENT','EMAIL_SEND_FAILED')
             ORDER BY a.created_at DESC LIMIT 1) AS sent_attempt_at
    FROM leads_raw lr
    WHERE lr.user_id = 4
      AND EXISTS (SELECT 1 FROM activity_log a WHERE a.lead_id = lr.id
                  AND a.action = 'DRAFT_GENERATED'
                  AND a.created_at BETWEEN '2026-08-18 09:00:00' AND '2026-08-18 09:05:00')
    ORDER BY lr.email_status, lr.id
""")
rows = cur.fetchall()
sent = [r for r in rows if r['email_status'] == 'SENT']
pend = [r for r in rows if r['email_status'] == 'PENDING_APPROVAL']
print(f"vertexventures batch: total={len(rows)} sent={len(sent)} pending={len(pend)} other={len(rows)-len(sent)-len(pend)}")
print()
print("=== SENT leads ===")
for r in sent[:20]:
    print(f"  id={r['id']} <{(r['email'] or '')[:50]}> user={r['user_id']} draft={'Y' if r['has_gmail_draft'] else 'N'} sent_at={r['sent_attempt_at']}")
print()
print("=== PENDING leads ===")
for r in pend[:20]:
    print(f"  id={r['id']} <{(r['email'] or '')[:50]}> user={r['user_id']} draft={'Y' if r['has_gmail_draft'] else 'N'} sent_attempt={r['sent_attempt_at']}")

cur.close()
conn.close()
