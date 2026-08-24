"""
Test the signature save flow exactly as the frontend does:
1. PUT /api/signatures/{id} (drafts.py update_signature)
2. PUT /api/auth/signature (auth.py legacy sync)

Uses a test marker and restores the original content afterwards.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

from app.database import get_db_connection
from app.api.drafts import update_signature, SignatureUpdateRequest
import psycopg2.extras

SIG_ID = 5  # kajal_default
MARKER = "SIG-SAVE-TEST-MARKER-abc789"


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT content FROM user_signatures WHERE id = %s", (SIG_ID,))
    row = cur.fetchone()
    if not row:
        print("FAIL: signature not found")
        return
    original = row["content"]

    try:
        # 1. Simulate the frontend PUT (content edit)
        edited = original + "\n\n" + MARKER
        req = SignatureUpdateRequest(name=None, content=edited)
        result = update_signature(SIG_ID, req, user_id="3")
        print("1. PUT /api/signatures/{id} -> saved:", MARKER in (result.get("content") or ""))

        # 2. Re-read from DB
        cur.execute("SELECT content FROM user_signatures WHERE id = %s", (SIG_ID,))
        db_content = cur.fetchone()["content"]
        print("2. DB content has marker:", MARKER in (db_content or ""))

        # 3. Legacy auth/signature sync (same call the frontend makes)
        from app.api.auth import SignatureUpdateRequest as AuthReq
        from app.api.auth import update_signature as auth_update_signature
        auth_result = auth_update_signature(AuthReq(signature=edited), user_id="3")
        print("3. PUT /api/auth/signature ->", auth_result.get("message"))

        cur.execute("SELECT signature FROM users WHERE id = 3")
        legacy = cur.fetchone()
        print("4. legacy users.signature has marker:", legacy is not None and MARKER in (legacy.get("signature") or ""))

        ok = MARKER in (db_content or "")
        print("\nRESULT:", "PASS" if ok else "FAIL")
    finally:
        # Restore
        try:
            update_signature(SIG_ID, SignatureUpdateRequest(name=None, content=original), user_id="3")
        except Exception as e:
            print("restore user_signatures error:", e)
        try:
            cur.execute("SELECT signature FROM users WHERE id = 3")
            legacy_orig = cur.fetchone()
            if legacy_orig:
                from app.api.auth import update_signature as au
                from app.api.auth import SignatureUpdateRequest as AR
                au(AR(signature=legacy_orig["signature"] or ""), user_id="3")
        except Exception as e:
            print("restore legacy error:", e)
        cur.close()
        conn.close()
        print("(original content restored)")


if __name__ == "__main__":
    main()
