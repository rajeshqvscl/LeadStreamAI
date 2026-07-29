"""
Script to clear optional attachments from signatures for Yashika, Kajal, and Vismaya.

Clears attachment_file from user_signatures table only (signature-level optional attachments).
Does NOT touch prompts/template attachments.

Run from backend/ directory:
    python scripts/clear_user_attachments.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_connection
import psycopg2.extras

# Users to clear signature attachments for
USERNAMES = ['yashika', 'kajal', 'vismaya']

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Clear attachment_file from user_signatures for these users
    print("=== CLEARING SIGNATURE OPTIONAL ATTACHMENTS ===\n")
    for uname in USERNAMES:
        # Resolve username to user_id
        cur.execute("SELECT id FROM users WHERE LOWER(username) LIKE LOWER(%s) LIMIT 1", (f"%{uname}%",))
        user_row = cur.fetchone()
        if not user_row:
            # Try by email prefix
            cur.execute("SELECT id FROM users WHERE LOWER(email) LIKE LOWER(%s) LIMIT 1", (f"{uname}%@%",))
            user_row = cur.fetchone()

        if user_row:
            user_id = int(user_row['id'])

            # First show what's currently set
            cur.execute(
                "SELECT id, name, attachment_file FROM user_signatures WHERE user_id = %s AND attachment_file IS NOT NULL",
                (user_id,)
            )
            current = cur.fetchall()
            if current:
                print(f"{uname} (ID={user_id}) — Current attachments:")
                for sig in current:
                    print(f"  Signature \"{sig['name']}\" (id={sig['id']}): {sig['attachment_file']}")
            else:
                print(f"{uname} (ID={user_id}): No signature attachments found (already clean)")

            # Clear all signature attachments
            cur.execute(
                "UPDATE user_signatures SET attachment_file = NULL, updated_at = NOW() WHERE user_id = %s AND attachment_file IS NOT NULL",
                (user_id,)
            )
            cleared = cur.rowcount
            conn.commit()
            if cleared > 0:
                print(f"  ✅ Cleared {cleared} signature attachment(s)\n")
            else:
                print(f"  Nothing to clear\n")
        else:
            print(f"{uname}: User not found in database\n")

    # Final verification
    print("\n=== VERIFICATION ===")
    any_remaining = False
    for uname in USERNAMES:
        cur.execute("""
            SELECT us.id, us.name, us.attachment_file, u.username
            FROM user_signatures us
            JOIN users u ON us.user_id = u.id
            WHERE LOWER(u.username) LIKE LOWER(%s) AND us.attachment_file IS NOT NULL
        """, (f"%{uname}%",))
        remaining = cur.fetchall()
        if remaining:
            any_remaining = True
            for r in remaining:
                print(f"  ❌ {r['username']}/{r['name']} (id={r['id']}): STILL HAS {r['attachment_file']}")
        else:
            print(f"  ✅ {uname}: All clear")

    cur.close()
    conn.close()

    if not any_remaining:
        print("\n✅ All signature optional attachments cleared successfully!")
    else:
        print("\n⚠️ Some attachments could not be cleared — check errors above.")

if __name__ == "__main__":
    main()
