"""Check current state of the 30 leads before scheduling for 17 Aug."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
for loc in ('app/.env', '.env'):
    if os.path.exists(loc):
        load_dotenv(loc)
        break
import psycopg2
from psycopg2.extras import RealDictCursor

url = os.getenv('DATABASE_URL','').strip().strip(chr(39)).strip(chr(34)).replace('postgres://','postgresql://',1)
conn = psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()
ids = [18578,18553,18547,18590,18537,18548,18564,18540,18575,18544,
       18565,18583,18555,18546,18586,18566,18554,18581,18545,18567,
       18585,18539,18568,18550,18591,18542,18551,18573,18552,18582]

cur.execute("""
    SELECT id, first_name, last_name, email, followup_stage, followup_status,
           email_status, last_outreach_at, lead_type, draft_template_used,
           is_responded, replied_at, scheduled_at,
           LEFT(COALESCE(email_draft,''), 100) AS draft_prefix,
           LEFT(COALESCE(followup_draft,''), 100) AS fu_prefix
    FROM leads_raw WHERE id = ANY(%s::int[]) ORDER BY id
""", (ids,))
rows = cur.fetchall()
print('Total:', len(rows))
for r in rows:
    loa = str(r['last_outreach_at'])[:19] if r['last_outreach_at'] else None
    print(f"{r['id']} | {r['first_name']} {r['last_name']} | stage={r['followup_stage']} "
          f"fs={r['followup_status']} est={r['email_status']} | loa={loa} | "
          f"lt={r['lead_type']} | tpl={r['draft_template_used']}")
    print(f"    email_draft: {r['draft_prefix']!r}")
    print(f"    followup_draft: {r['fu_prefix']!r}")
    print(f"    scheduled_at={r['scheduled_at']} responded={r['is_responded']} replied_at={r['replied_at']}")

print('---aggregate---')
cur.execute("""
    SELECT COUNT(*) AS n,
           COUNT(*) FILTER (WHERE followup_draft IS NOT NULL AND followup_draft != '') AS has_fu_draft,
           COUNT(*) FILTER (WHERE email_draft IS NOT NULL AND email_draft != '') AS has_draft
    FROM leads_raw WHERE id = ANY(%s::int[])
""", (ids,))
print(dict(cur.fetchone()))
cur.close()
conn.close()
