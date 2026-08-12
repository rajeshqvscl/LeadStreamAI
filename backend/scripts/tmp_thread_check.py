import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv('app/.env')
import psycopg2
from psycopg2.extras import RealDictCursor

url = os.getenv('DATABASE_URL', '').strip().strip(chr(39)).strip(chr(34)).replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

print("=== Old ACTIVE stuck leads: gmail_thread_id present? ===")
cur.execute("""
    SELECT
      CASE WHEN l.gmail_thread_id IS NOT NULL AND l.gmail_thread_id != '' THEN 'HAS_THREAD' ELSE 'NO_THREAD' END AS thread,
      CASE WHEN position(chr(10) IN l.email) > 0 OR position(';' IN l.email) > 0 OR position(',' IN l.email) > 0 THEN 'MULTI' ELSE 'SINGLE' END AS email_type,
      COUNT(*) AS n
    FROM leads_raw l
    WHERE l.followup_status='ACTIVE' AND COALESCE(l.is_responded,FALSE)=FALSE
      AND l.last_outreach_at IS NOT NULL AND l.last_outreach_at < '2026-07-01'
    GROUP BY 1,2 ORDER BY 1,2
""")
for r in cur.fetchall():
    print(f"  {r['thread']:<12} {r['email_type']:<8} {r['n']}")

print("\n=== NO_THREAD single-email stuck leads: do they have EMAIL_SENT logs? ===")
cur.execute("""
    SELECT
      CASE WHEN es.lead_id IS NOT NULL THEN 'EMAIL_SENT_LOGGED' ELSE 'NO_EMAIL_SENT_LOG' END AS sent_log,
      COUNT(*) AS n
    FROM leads_raw l
    LEFT JOIN (SELECT DISTINCT lead_id FROM activity_log WHERE action='EMAIL_SENT') es ON es.lead_id = l.id
    WHERE l.followup_status='ACTIVE' AND COALESCE(l.is_responded,FALSE)=FALSE
      AND l.last_outreach_at IS NOT NULL AND l.last_outreach_at < '2026-07-01'
      AND (l.gmail_thread_id IS NULL OR l.gmail_thread_id = '')
      AND position(chr(10) IN l.email)=0 AND position(';' IN l.email)=0 AND position(',' IN l.email)=0
    GROUP BY 1
""")
for r in cur.fetchall():
    print(f"  {r['sent_log']}: {r['n']}")

print("\n=== Sample: stuck lead 2385 (abhay@piperserica.com) full state ===")
cur.execute("""
    SELECT l.id, l.email, l.gmail_thread_id, l.gmail_message_id, l.followup_stage, l.followup_status,
           l.last_outreach_at, l.first_outreach_at, l.email_status,
           (SELECT COUNT(*) FROM activity_log al WHERE al.lead_id=l.id) n_logs
    FROM leads_raw l WHERE l.id = 2385
""")
r = cur.fetchone()
for k, v in r.items():
    print(f"  {k}: {str(v)[:60]}")
cur.execute("SELECT action, details, created_at FROM activity_log WHERE lead_id = 2385 ORDER BY created_at DESC LIMIT 6")
for a in cur.fetchall():
    print(f"  LOG {a['created_at']} | {a['action']} | {(a['details'] or '')[:60]}")

cur.close(); conn.close()
