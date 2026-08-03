"""Diagnostic: why does the Google disconnect endpoint fail?"""
import sys
import os
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env", "../../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

sys.path.append(os.getcwd())

from app.database import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

# 1. Which google_* columns exist in users?
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='users' AND column_name LIKE 'google_%' ORDER BY column_name"
)
cols = [r['column_name'] for r in cur.fetchall()]
print("google_* columns present:", cols)

REQUIRED = [
    "google_access_token",
    "google_refresh_token",
    "google_token_expiry",
    "google_linked_at",
    "google_email",
]
missing = [c for c in REQUIRED if c not in cols]
print("MISSING columns for disconnect:", missing if missing else "none")

# 2. Test the exact disconnect UPDATE (wrapped in a savepoint + rollback so nothing changes)
try:
    cur.execute("SAVEPOINT test_disconnect")
    cur.execute(
        "UPDATE users SET google_access_token = NULL, google_refresh_token = NULL, "
        "google_token_expiry = NULL, google_linked_at = NULL, google_email = NULL WHERE id = 1"
    )
    print("disconnect UPDATE rowcount:", cur.rowcount)
    cur.execute("ROLLBACK TO SAVEPOINT test_disconnect")
except Exception as e:
    conn.rollback()
    print("disconnect UPDATE FAILED:", type(e).__name__, str(e))

# 2b. Test the NEW schema-robust dynamic SET-clause logic (same as the fixed endpoint)
try:
    cur.execute("SAVEPOINT test_disconnect_dynamic")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name LIKE 'google_%'"
    )
    available = {r['column_name'] for r in cur.fetchall()}
    target_cols = [
        "google_access_token", "google_refresh_token", "google_token_expiry",
        "google_linked_at", "google_email",
    ]
    settable = [c for c in target_cols if c in available]
    set_clause = ", ".join(f"{c} = NULL" for c in settable)
    cur.execute(f"UPDATE users SET {set_clause} WHERE id = 1")
    print("DYNAMIC disconnect UPDATE ok — rowcount:", cur.rowcount, "| columns used:", settable)
    cur.execute("ROLLBACK TO SAVEPOINT test_disconnect_dynamic")
except Exception as e:
    conn.rollback()
    print("DYNAMIC disconnect UPDATE FAILED:", type(e).__name__, str(e))

# 3. Any users currently connected? (for reference)
cur.execute(
    "SELECT id, username, google_email, google_linked_at IS NOT NULL AS linked "
    "FROM users WHERE google_refresh_token IS NOT NULL ORDER BY id"
)
print("\nUsers with Google tokens:")
for r in cur.fetchall():
    print(f"  id={r['id']} | {r['username']} | linked={r['linked']} | email={r['google_email']}")

cur.close()
conn.close()
print("\nDone.")
