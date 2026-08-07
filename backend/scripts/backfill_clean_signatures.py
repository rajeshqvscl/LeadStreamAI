"""
One-off backfill: normalize stored signature content to clean markdown.

Why: some saved signatures are a mix of raw HTML (<span style="..."> wrappers)
and markdown (***Name***, [Website](url)). That mixed content shows up as raw
markup in the signature editor textarea and leaks raw markdown into drafts.

This script runs clean_signature_markdown (the same normalization applied at
save time) over every stored signature. Dry-run by default; pass --apply to
write the cleaned content back to the database.

Usage:
    python scripts/backfill_clean_signatures.py            # dry run
    python scripts/backfill_clean_signatures.py --apply    # write changes
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", ".env")))

from app.database import get_db_connection
from app.utils.signature_clean import clean_signature_markdown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write cleaned content to DB (default: dry run)")
    args = ap.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, sig_type, content FROM user_signatures ORDER BY id")
    sig_rows = cur.fetchall()
    cur.execute("SELECT id, username, signature FROM users ORDER BY id")
    user_rows = cur.fetchall()

    changed_sigs = 0
    changed_users = 0

    print(f"=== user_signatures ({len(sig_rows)} rows) ===")
    for r in sig_rows:
        sig_id, name, sig_type, content = r["id"], r["name"], r["sig_type"], r["content"]
        cleaned = clean_signature_markdown(content or "")
        if cleaned != (content or ""):
            changed_sigs += 1
            print(f"  SIG id={sig_id} name={name!r} type={sig_type}:")
            print(f"    BEFORE: {repr((content or '')[:160])}")
            print(f"    AFTER:  {repr(cleaned[:160])}")
            if args.apply:
                cur.execute("UPDATE user_signatures SET content = %s WHERE id = %s", (cleaned, sig_id))

    print(f"\n=== users.signature ({len(user_rows)} rows) ===")
    for r in user_rows:
        uid, username, signature = r["id"], r["username"], r["signature"]
        cleaned = clean_signature_markdown(signature or "")
        if cleaned != (signature or ""):
            changed_users += 1
            print(f"  USER id={uid} username={username!r}:")
            print(f"    BEFORE: {repr((signature or '')[:160])}")
            print(f"    AFTER:  {repr(cleaned[:160])}")
            if args.apply:
                cur.execute("UPDATE users SET signature = %s WHERE id = %s", (cleaned, uid))

    if args.apply:
        conn.commit()
        print(f"\nAPPLIED: {changed_sigs} signatures + {changed_users} users updated.")
    else:
        print(f"\nDRY RUN: {changed_sigs} signatures + {changed_users} users would change (pass --apply to write).")

    conn.close()


if __name__ == "__main__":
    main()
