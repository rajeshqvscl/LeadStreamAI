"""Report the exact 22 named emails: which exist under Kajal (user_id=3), their state,
and whether they are covered in the global unsubscribe_list."""
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

print("=" * 100)
print("EXACT 22 NAMED EMAILS - Kajal account (user_id=3) coverage")
print("=" * 100)
print(f"{'Email':<40} {'In Kajal':<10} {'Status':<12} {'Replied':<8} {'Intent':<20} {'UnsubList'}")
print("-" * 100)
for em in EMAILS:
    cur.execute("""
        SELECT id, first_name, last_name, email, followup_status, is_responded, reply_intent,
               is_unsubscribed, email_opt_in, user_id
        FROM leads_raw WHERE LOWER(email) = LOWER(%s) ORDER BY user_id
    """, (em,))
    leads = cur.fetchall()
    cur.execute("SELECT 1 FROM unsubscribe_list WHERE LOWER(email) = LOWER(%s)", (em,))
    in_list = cur.fetchone() is not None
    if not leads:
        print(f"{em:<40} {'NO':<10} {'-':<12} {'-':<8} {'-':<20} {str(in_list)}")
    else:
        for l in leads:
            owned = "YES" if l['user_id'] == 3 else f"user{l['user_id']}"
            print(f"{em:<40} {owned:<10} {(l['followup_status'] or '-'):<12} {str(bool(l['is_responded'])):<8} {(l['reply_intent'] or '-'):<20} {str(in_list)}")

# Any of the 22 that exist under OTHER users too (global block side effect check)
print("\n[GLOBAL SIDE-EFFECT CHECK] Same named emails under OTHER accounts:")
cur.execute("""
    SELECT u.username, l.email, l.followup_status, l.is_unsubscribed, l.email_opt_in
    FROM leads_raw l JOIN users u ON l.user_id = u.id
    WHERE LOWER(l.email) IN (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
      AND l.user_id != 3
    ORDER BY l.email
""", tuple(e.lower() for e in EMAILS))
rows = cur.fetchall()
if not rows:
    print("  (none - the 22 named emails exist only under Kajal's account)")
for r in rows:
    print(f"  {r['username']:<14} | {r['email']:<40} | {r['followup_status']} | unsub={r['is_unsubscribed']} | optin={r['email_opt_in']}")

cur.close()
conn.close()
print("\nDONE")
