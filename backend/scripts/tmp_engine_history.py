import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv('app/.env')
import psycopg2
from psycopg2.extras import RealDictCursor

url = os.getenv('DATABASE_URL', '').strip().strip(chr(39)).strip(chr(34)).replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

print("=== AUTO_FOLLOWUP_SENT by month (engine sends) ===")
cur.execute("""
    SELECT TO_CHAR(al.created_at, 'YYYY-MM') AS month, COUNT(*) AS n
    FROM activity_log al
    WHERE al.action = 'AUTO_FOLLOWUP_SENT'
    GROUP BY 1 ORDER BY 1
""")
for r in cur.fetchall():
    print(f"  {r['month']}: {r['n']}")

print("\n=== AUTO_FOLLOWUP_SENT by user per month (June-July) ===")
cur.execute("""
    SELECT u.username, TO_CHAR(al.created_at, 'YYYY-MM') AS month, COUNT(*) AS n
    FROM activity_log al JOIN users u ON u.id = al.user_id
    WHERE al.action = 'AUTO_FOLLOWUP_SENT' AND al.created_at >= '2026-05-01' AND al.created_at < '2026-08-01'
    GROUP BY 1,2 ORDER BY 2,1
""")
for r in cur.fetchall():
    print(f"  {r['month']} | {r['username']:<12} {r['n']}")

print("\n=== Any auto-pilot toggle logs in activity_log? ===")
cur.execute("""
    SELECT action, details, created_at FROM activity_log
    WHERE LOWER(COALESCE(details,'')) LIKE '%auto%pilot%' OR LOWER(COALESCE(details,'')) LIKE '%auto_followup%'
       OR LOWER(action) LIKE '%auto%' OR LOWER(action) LIKE '%setting%' OR LOWER(action) LIKE '%pilot%'
    ORDER BY created_at DESC LIMIT 15
""")
rows = cur.fetchall()
if not rows:
    print("  (no toggle log found)")
else:
    for r in rows:
        print(f"  {r['created_at']} | {r['action']} | {(r['details'] or '')[:80]}")

print("\n=== 552 old pipeline leads: owner breakdown ===")
cur.execute("""
    SELECT u.username, l.followup_status, COUNT(*) n
    FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id
    WHERE l.followup_status IN ('ACTIVE', 'SCHEDULED', 'PENDING_APPROVAL', 'APPROVED')
      AND COALESCE(l.is_responded, FALSE) = FALSE
      AND l.last_outreach_at IS NOT NULL
      AND l.last_outreach_at < '2026-07-01'
    GROUP BY 1,2 ORDER BY 2,1
""")
for r in cur.fetchall():
    print(f"  {r['username'] or '?'}: {r['followup_status']} = {r['n']}")

print("\n=== Oldest 8 ACTIVE June leads: their email_status (engine eligibility) ===")
cur.execute("""
    SELECT l.id, u.username, l.email, l.followup_stage, l.email_status, l.last_outreach_at,
           (SELECT COUNT(*) FROM activity_log al WHERE al.lead_id = l.id AND al.action = 'AUTO_FOLLOWUP_SENT') AS fu_sent
    FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id
    WHERE l.followup_status = 'ACTIVE' AND COALESCE(l.is_responded,FALSE)=FALSE
      AND l.last_outreach_at IS NOT NULL AND l.last_outreach_at < '2026-07-01'
    ORDER BY l.last_outreach_at ASC LIMIT 8
""")
for r in cur.fetchall():
    print(f"  {r['id']} | {r['username'] or '?'} | {r['email']} | stage={r['followup_stage']} email={r['email_status']} | last={r['last_outreach_at']} | fu_sent={r['fu_sent']}")

cur.close(); conn.close()
