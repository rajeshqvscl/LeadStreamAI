"""
Move leads - handle unique constraint conflicts.
If a lead with same email already exists under target user, delete from Yashika's account.
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

# Check each lead for conflicts
moves = {
    3: [2498, 2499, 7749],  # Kajal
    2: [478, 7609]           # Ayush
}

for target_uid, lead_ids in moves.items():
    target_name = "Kajal" if target_uid == 3 else "Ayush"
    print(f"\n=== Processing leads for {target_name} (user_id={target_uid}) ===")
    
    for lid in lead_ids:
        # Get lead email
        cur.execute("SELECT id, email, first_name, last_name FROM leads_raw WHERE id = %s AND user_id = 4", (lid,))
        lead = cur.fetchone()
        if not lead:
            print(f"  ID {lid}: Not found under Yashika's account")
            continue
        
        email = lead['email']
        name = f"{lead['first_name']} {lead['last_name']}"
        
        # Check if this email already exists under target user
        cur.execute("SELECT id FROM leads_raw WHERE LOWER(email) = LOWER(%s) AND user_id = %s", (email, target_uid))
        existing = cur.fetchone()
        
        if existing:
            # Conflict - delete from Yashika's account since it already exists under target
            print(f"  ID {lid} ({name} - {email}): Already exists under {target_name} (ID {existing['id']})")
            print(f"    -> DELETING from Yashika's account")
            cur.execute("DELETE FROM leads_raw WHERE id = %s AND user_id = 4", (lid,))
            print(f"    -> Deleted OK")
        else:
            # No conflict - move to target user
            print(f"  ID {lid} ({name} - {email}): Moving to {target_name}")
            cur.execute("""
                UPDATE leads_raw SET user_id = %s, updated_at = NOW()
                WHERE id = %s AND user_id = 4
            """, (target_uid, lid))
            if cur.rowcount > 0:
                print(f"    -> Moved OK")
            else:
                print(f"    -> Failed")

conn.commit()

# Verify
print("\n=== VERIFICATION ===")
for target_uid, lead_ids in moves.items():
    target_name = "Kajal" if target_uid == 3 else "Ayush"
    for lid in lead_ids:
        cur.execute("SELECT id, user_id FROM leads_raw WHERE id = %s", (lid,))
        l = cur.fetchone()
        if l:
            owner = "Yashika" if l['user_id'] == 4 else (target_name if l['user_id'] == target_uid else f"User_{l['user_id']}")
            print(f"  ID {lid} -> {owner} (user_id={l['user_id']})")
        else:
            print(f"  ID {lid} -> DELETED (was duplicate)")

# Also check ID 1771 wasn't touched
cur.execute("SELECT id, user_id FROM leads_raw WHERE id = 1771")
l = cur.fetchone()
if l:
    print(f"\n  ID 1771 (Vartul Jain) -> {'NOT MOVED' if l['user_id'] == 4 else 'ACCIDENTALLY MOVED!'}")

cur.close()
conn.close()
print("\nDone!")
