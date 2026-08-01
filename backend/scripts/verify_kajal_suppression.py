"""Verify the Kajal-account suppression was applied correctly."""
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

EMAILS = [
    "moreshwar.panchal@niifindia.in", "pranav@3one4capital.com", "padmaja@iangroup.vc",
    "yournest@yournest.in", "sasha@elev8vp.com", "vidit@anayventures.com",
    "aditya.arora@faad.in", "jehangir@sekhsaria.com", "jordan@motier.vc",
    "vishal.katariya@ankurcapital.com", "sharad.yadav@chimeravc.com", "anurag@bvp.com",
    "deals@dexter.ventures", "nihal.shetty@zerodha.com", "samir@atheravp.com",
    "robin@cornucopiacapital.com", "deepak@catamaran.in", "ATrehan@act.is",
    "mahesh@amicuscapital.in", "rahul@stellarisvp.com", "ea@ankurcapital.com",
    "animesh@udyatventures.com",
]
DOMAINS = sorted({e.strip().lower().split('@')[-1] for e in EMAILS if '@' in e})
ph = ','.join(['%s'] * len(EMAILS))
dph = ','.join(['%s'] * len(DOMAINS))
email_lower = [e.lower() for e in EMAILS]

cur.execute(f"""
    SELECT followup_status, COUNT(*) as cnt
    FROM leads_raw
    WHERE user_id = 3
      AND (LOWER(email) IN ({ph}) OR LOWER(domain) IN ({dph}) OR LOWER(SPLIT_PART(email, '@', 2)) IN ({dph}))
    GROUP BY followup_status ORDER BY cnt DESC
""", email_lower + DOMAINS + DOMAINS)
print("[STATUS BREAKDOWN] (Kajal account, matched leads):")
for r in cur.fetchall():
    print(f"  {r['followup_status'] or 'NONE':<18} {r['cnt']}")

# Any still-active?
cur.execute(f"""
    SELECT id, first_name, last_name, email, followup_status, is_unsubscribed, email_opt_in
    FROM leads_raw
    WHERE user_id = 3
      AND (LOWER(email) IN ({ph}) OR LOWER(domain) IN ({dph}) OR LOWER(SPLIT_PART(email, '@', 2)) IN ({dph}))
      AND (followup_status IN ('ACTIVE', 'SCHEDULED', 'PENDING_APPROVAL', 'APPROVED')
           OR COALESCE(is_unsubscribed, FALSE) = FALSE
           OR COALESCE(email_opt_in, TRUE) = TRUE)
    ORDER BY id
""", email_lower + DOMAINS + DOMAINS)
rows = cur.fetchall()
print(f"\n[REMAINING NOT-SUPPRESSED] (should be 0): {len(rows)}")
for r in rows:
    print(f"  ID {r['id']} | {r['first_name']} {r['last_name']} | {r['email']} | {r['followup_status']} | unsub={r['is_unsubscribed']} | optin={r['email_opt_in']}")

# unsubscribe_list coverage for Kajal's matched emails
cur.execute(f"""
    SELECT COUNT(*) as total FROM unsubscribe_list
    WHERE LOWER(email) IN (
        SELECT DISTINCT LOWER(email) FROM leads_raw
        WHERE user_id = 3
          AND (LOWER(email) IN ({ph}) OR LOWER(domain) IN ({dph}) OR LOWER(SPLIT_PART(email, '@', 2)) IN ({dph}))
    )
""", email_lower + DOMAINS + DOMAINS)
print(f"\n[UNSUBSCRIBE_LIST] Kajal matched emails present: {cur.fetchone()['total']}")

# activity log audit trail
cur.execute("""
    SELECT COUNT(*) as cnt FROM activity_log
    WHERE action = 'FOLLOWUP_STOPPED' AND details LIKE 'Manual suppression%'
""")
print(f"[ACTIVITY LOG] suppression audit entries: {cur.fetchone()['cnt']}")

cur.close()
conn.close()
print("\nVERIFICATION DONE")
