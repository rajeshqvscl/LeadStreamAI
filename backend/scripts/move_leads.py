"""
Move leads from Yashika's account to the correct user accounts.

Kajal ke leads (user_id=3): IDs 2498, 2499, 7749
Ayush ke leads (user_id=2): IDs 478, 7609
"""
import sys, os
from dotenv import load_dotenv

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import psycopg2
from psycopg2.extras import RealDictCursor

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found")
    sys.exit(1)

db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# Move leads to Kajal (user_id=3)
kajal_ids = [2498, 2499, 7749]
print(f"Moving {len(kajal_ids)} leads to Kajal (user_id=3)...")
for lid in kajal_ids:
    cur.execute("""
        UPDATE leads_raw SET user_id = 3, updated_at = NOW()
        WHERE id = %s AND user_id = 4
        RETURNING id, first_name, last_name, email
    """, (lid,))
    row = cur.fetchone()
    if row:
        print(f"  Moved ID {row['id']} - {row['first_name']} {row['last_name']} ({row['email']}) to Kajal")
    else:
        print(f"  ID {lid} not found or not under Yashika's account")

# Move leads to Ayush (user_id=2)
ayush_ids = [478, 7609]
print(f"\nMoving {len(ayush_ids)} leads to Ayush (user_id=2)...")
for lid in ayush_ids:
    cur.execute("""
        UPDATE leads_raw SET user_id = 2, updated_at = NOW()
        WHERE id = %s AND user_id = 4
        RETURNING id, first_name, last_name, email
    """, (lid,))
    row = cur.fetchone()
    if row:
        print(f"  Moved ID {row['id']} - {row['first_name']} {row['last_name']} ({row['email']}) to Ayush")
    else:
        print(f"  ID {lid} not found or not under Yashika's account")

conn.commit()

# Verify
print("\n=== VERIFICATION ===")
all_ids = kajal_ids + ayush_ids
for lid in all_ids:
    cur.execute("SELECT id, user_id FROM leads_raw WHERE id = %s", (lid,))
    l = cur.fetchone()
    if l:
        owner = "Kajal" if l['user_id'] == 3 else ("Ayush" if l['user_id'] == 2 else ("Yashika" if l['user_id'] == 4 else f"User_{l['user_id']}"))
        print(f"  ID {l['id']} -> {owner} (user_id={l['user_id']}) ✅")
    else:
        print(f"  ID {lid} -> NOT FOUND ❌")

# Check ID 1771 was NOT moved (should remain under Yashika)
cur.execute("SELECT id, user_id FROM leads_raw WHERE id = 1771")
l = cur.fetchone()
if l:
    print(f"\n  ID 1771 (Vartul Jain) -> {'NOT MOVED' if l['user_id'] == 4 else 'WAS MOVED!'} (user_id={l['user_id']})")

cur.close()
conn.close()
print("\nDone!")
