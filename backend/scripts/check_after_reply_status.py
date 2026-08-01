"""For the leads where a follow-up was confirmed sent AFTER their reply (Yashika/Palak),
show their CURRENT followup_status so we know if more follow-ups could still go out."""
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
if not db_url:
    print("DATABASE_URL not found")
    sys.exit(1)
db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# Leads confirmed to have received a follow-up after replying (from prior diagnostic)
CONFIRMED_IDS = [
    # Yashika (user_id=4)
    16465, 11615, 7636, 7747, 7753, 10541, 7633, 4923, 337, 11614,
    11699, 10574, 5050, 10024, 6992, 7613, 7391, 11096, 11139, 7823,
    6965, 7062, 8897, 3767, 3695, 3082, 1355, 691, 680, 8488,
    # Palak (user_id=5)
    10441, 5672, 4148, 4139, 4283, 5688, 5713, 4268,
]

cur.execute("""
    SELECT l.id, l.first_name, l.last_name, l.email, l.user_id, u.username,
           l.followup_status, l.followup_stage, l.email_status, l.reply_intent,
           l.is_responded, l.is_unsubscribed, l.email_opt_in,
           l.last_outreach_at,
           (SELECT MAX(created_at) FROM activity_log WHERE lead_id = l.id AND action IN ('AUTO_FOLLOWUP_SENT','FOLLOWUP_APPROVED','FOLLOWUP_SENT')) as last_followup_send
    FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id
    WHERE l.id = ANY(%s::int[])
    ORDER BY l.user_id, l.id
""", (CONFIRMED_IDS,))
rows = cur.fetchall()

print("=" * 120)
print("CURRENT STATUS of leads that received a follow-up AFTER replying")
print("=" * 120)
for r in rows:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    uid = r['user_id']
    acct = r['username'] or '?'
    still = (r['followup_status'] or '').upper() in ('ACTIVE', 'SCHEDULED', 'PENDING_APPROVAL', 'APPROVED')
    mark = "STILL-ACTIVE" if still else "stopped"
    print(f"  [{acct:<10}] ID {r['id']:>6} | {name:<24} | {r['email']:<42} | intent={r['reply_intent'] or '-':<18} | {r['followup_status'] or '-':<16} | stage={r['followup_stage']} | unsub={bool(r['is_unsubscribed'])} | => {mark}")
    print(f"      last_outreach={r['last_outreach_at']} | last_followup_send={r['last_followup_send']}")

still = [r for r in rows if (r['followup_status'] or '').upper() in ('ACTIVE', 'SCHEDULED', 'PENDING_APPROVAL', 'APPROVED')]
print(f"\n[STILL ELIGIBLE FOR MORE FOLLOWUPS]: {len(still)}")
for r in still:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"  [{r['username'] or '?'}] ID {r['id']} | {name} | {r['email']} | intent={r['reply_intent']} | {r['followup_status']} | stage={r['followup_stage']}")

cur.close()
conn.close()
print("\nDONE")
