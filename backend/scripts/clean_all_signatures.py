"""
Clean ALL users' signatures (user_signatures + legacy users.signature):
converts any WYSIWYG HTML (<br>, <span>, &nbsp;, <div>, ...) to clean markdown
using the same shared utility that now runs on every save.

Run from backend/:
    python scripts/clean_all_signatures.py            # read-only: show what would change
    python scripts/clean_all_signatures.py --apply    # apply the cleanup
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

from app.database import get_db_connection
from app.utils.signature_clean import clean_signature_markdown
import psycopg2.extras


def main():
    parser = argparse.ArgumentParser(description="Clean HTML from all saved signatures")
    parser.add_argument("--apply", action="store_true", help="Write changes to DB (default is read-only)")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── user_signatures table ──
    cur.execute("SELECT id, user_id, content FROM user_signatures ORDER BY id")
    rows = cur.fetchall()
    changed = 0
    print(f"=== user_signatures ({len(rows)} rows) ===")
    for r in rows:
        old = r["content"] or ""
        new = clean_signature_markdown(old)
        if new != old:
            changed += 1
            print(f"  sig={r['id']} user={r['user_id']}: CHANGED")
            print(f"    BEFORE: {(old[:140]).replace(chr(10), chr(92)+'n')!r}")
            print(f"    AFTER:  {(new[:140]).replace(chr(10), chr(92)+'n')!r}")
            if args.apply:
                cur.execute("UPDATE user_signatures SET content = %s, updated_at = NOW() WHERE id = %s", (new, r["id"]))
        else:
            print(f"  sig={r['id']} user={r['user_id']}: clean (no change)")
    print(f"  -> {changed} signature(s) need cleaning")

    # ── legacy users.signature column ──
    cur.execute("SELECT id, username, signature FROM users WHERE signature IS NOT NULL AND signature != ''")
    rows = cur.fetchall()
    legacy_changed = 0
    print(f"\n=== legacy users.signature ({len(rows)} rows) ===")
    for r in rows:
        old = r["signature"] or ""
        new = clean_signature_markdown(old)
        if new != old:
            legacy_changed += 1
            print(f"  user={r['id']} ({r['username']}): CHANGED")
            print(f"    BEFORE: {(old[:140]).replace(chr(10), chr(92)+'n')!r}")
            print(f"    AFTER:  {(new[:140]).replace(chr(10), chr(92)+'n')!r}")
            if args.apply:
                cur.execute("UPDATE users SET signature = %s WHERE id = %s", (new, r["id"]))
        else:
            print(f"  user={r['id']} ({r['username']}): clean (no change)")
    print(f"  -> {legacy_changed} legacy signature(s) need cleaning")

    if args.apply:
        conn.commit()
        print(f"\nApplied: {changed} signature(s) + {legacy_changed} legacy cleaned & committed.")
    else:
        print("\n(Read-only - no changes made. Run with --apply to save.)")

    conn.close()


if __name__ == "__main__":
    main()
