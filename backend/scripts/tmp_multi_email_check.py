import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv('app/.env')
import psycopg2
from psycopg2.extras import RealDictCursor

url = os.getenv('DATABASE_URL', '').strip().strip(chr(39)).strip(chr(34)).replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

print("=== Old ACTIVE leads: multi-email vs single ===")
cur.execute("""
    SELECT
      CASE WHEN position(chr(10) IN l.email) > 0 OR position(';' IN l.email) > 0 OR position(',' IN l.email) > 0 THEN 'MULTI' ELSE 'SINGLE' END AS email_type,
      COUNT(*) AS n
    FROM leads_raw l
    WHERE l.followup_status = 'ACTIVE' AND COALESCE(l.is_responded,FALSE)=FALSE
      AND l.last_outreach_at IS NOT NULL AND l.last_outreach_at < '2026-07-01'
    GROUP BY 1
""")
for r in cur.fetchall():
    print(f"  {r['email_type']}: {r['n']}")

print("\n=== Sample SINGLE-email stuck ACTIVE leads (fu_sent=0) ===")
cur.execute("""
    SELECT l.id, u.username, l.email, l.followup_stage, l.email_status, l.last_outreach_at,
           (SELECT COUNT(*) FROM activity_log al WHERE al.lead_id=l.id AND al.action='AUTO_FOLLOWUP_SENT') fu_sent,
           (SELECT COUNT(*) FROM activity_log al WHERE al.lead_id=l.id) n_logs
    FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id
    WHERE l.followup_status='ACTIVE' AND COALESCE(l.is_responded,FALSE)=FALSE
      AND l.last_outreach_at IS NOT NULL AND l.last_outreach_at < '2026-07-01'
      AND position(chr(10) IN l.email)=0 AND position(';' IN l.email)=0 AND position(',' IN l.email)=0
    ORDER BY l.last_outreach_at ASC LIMIT 8
""")
for r in cur.fetchall():
    print(f"  {r['id']} | {r['username'] or '?'} | {r['email']} | stage={r['followup_stage']} email={r['email_status']} | last={r['last_outreach_at']} | fu_sent={r['fu_sent']} logs={r['n_logs']}")

print("\n=== One stuck lead's full activity timeline (id 1973) ===")
cur.execute("SELECT action, details, created_at FROM activity_log WHERE lead_id = 1973 ORDER BY created_at DESC LIMIT 12")
for r in cur.fetchall():
    print(f"  {r['created_at']} | {r['action']} | {(r['details'] or '')[:70]}")

print("\n=== Multi-email stuck leads count by owner ===")
cur.execute("""
    SELECT u.username, COUNT(*) n
    FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id
    WHERE l.followup_status='ACTIVE' AND COALESCE(l.is_responded,FALSE)=FALSE
      AND l.last_outreach_at IS NOT NULL AND l.last_outreach_at < '2026-07-01'
      AND (position(chr(10) IN l.email) > 0 OR position(';' IN l.email) > 0 OR position(',' IN l.email) > 0)
    GROUP BY 1
""")
for r in cur.fetchall():
    print(f"  {r['username'] or '?'}: {r['n']}")

cur.close(); conn.close()
