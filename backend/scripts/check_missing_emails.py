"""Check the 5 named emails that had no Kajal lead. If they don't exist under ANY
account, add them to the global unsubscribe_list so they can never be ingested/followed up."""
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

APPLY = '--apply' in sys.argv
MISSING = [
    "padmaja@iangroup.vc",
    "sasha@elev8vp.com",
    "jehangir@sekhsaria.com",
    "mahesh@amicuscapital.in",
    "ea@ankurcapital.com",
]

print(f"MODE: {'APPLY' if APPLY else 'READ-ONLY'}")
for em in MISSING:
    cur.execute("""
        SELECT l.id, l.user_id, u.username, l.followup_status, l.email_status, l.is_responded, l.reply_intent
        FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id
        WHERE LOWER(l.email) = LOWER(%s) ORDER BY l.user_id
    """, (em,))
    leads = cur.fetchall()
    cur.execute("SELECT 1 FROM unsubscribe_list WHERE LOWER(email) = LOWER(%s)", (em,))
    in_list = cur.fetchone() is not None
    print(f"\n{em}")
    if not leads:
        print("  exists as lead: NO (nowhere in DB)")
    else:
        for l in leads:
            print(f"  lead id={l['id']} | user={l['user_id']} ({l['username']}) | {l['followup_status']} | {l['email_status']} | replied={l['is_responded']} | {l['reply_intent']}")
    print(f"  in unsubscribe_list: {in_list}")

if APPLY:
    added = 0
    for em in MISSING:
        cur.execute("SELECT 1 FROM leads_raw WHERE LOWER(email) = LOWER(%s)", (em,))
        if cur.fetchone():
            print(f"  SKIP {em} - exists as a lead somewhere, not adding globally")
            continue
        cur.execute("""
            INSERT INTO unsubscribe_list (email, reason, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (em, "Investor do-not-followup (Series A+ ClimateTech campaign)", "manual_suppression"))
        added += cur.rowcount
    conn.commit()
    print(f"\nAdded {added} previously-absent named emails to unsubscribe_list.")

cur.close()
conn.close()
print("DONE")
