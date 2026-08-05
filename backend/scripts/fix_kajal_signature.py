"""
Remove extra <br> tags from Kajal's signature(s).

Kajal's saved signature is the odd one out: every line ends with a <br> tag AND
is followed by a newline (double line breaks), and lines are wrapped in
<span style="color:#000000;">…</span>. All other team members' signatures are
plain markdown with no <br> and no span wrappers.

This script converts Kajal's signature to that standard plain-markdown format:
  - replaces every <br> with a newline
  - strips <span style="color:#000000;">…</span> wrappers
  - collapses consecutive blank lines and trims leading/trailing whitespace

Fixes BOTH the user_signatures row and the legacy users.signature column.

Run from backend/ directory:
    python scripts/fix_kajal_signature.py            # read-only: show current signatures
    python scripts/fix_kajal_signature.py --apply    # apply the fix
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Authoritative env file lives at backend/app/.env (same as main.py)
env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

from app.database import get_db_connection
from app.utils.signature_clean import clean_signature_markdown
import psycopg2.extras

# Matches <br>, <br/>, <br />, <br > etc. (case-insensitive) — used only by preview()
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


# Re-export the shared cleanup (single source of truth in app/utils).
def to_standard_markdown(text: str) -> str:
    """Convert Kajal's span/<br>/div-wrapped signature to clean plain markdown.

    Delegates to app.utils.signature_clean.clean_signature_markdown — the same
    sanitizer now applied on every signature save — so scripts and API stay in
    sync. Handles BOTH legacy formats and the HTML emitted by the frontend
    WYSIWYG editor (ToolbarTextarea), which saves raw innerHTML: <div>…</div>,
    <span style="color: rgb(0, 0, 0);">…</span>, <br>, &nbsp;, &amp; etc.
    """
    return clean_signature_markdown(text)


def find_kajal(cur) -> int:
    """Resolve Kajal's user id (prefer known id 3, fall back to username/email match)."""
    cur.execute("SELECT id, username, full_name FROM users WHERE id = 3")
    row = cur.fetchone()
    if row:
        return int(row["id"])
    cur.execute("SELECT id FROM users WHERE LOWER(username) LIKE LOWER(%s) LIMIT 1", ("%kajal%",))
    row = cur.fetchone()
    if row:
        return int(row["id"])
    raise SystemExit("Kajal user not found in database")


def fetch_signatures(cur, user_id: int):
    """Return all user_signatures rows for the user (real dicts)."""
    cur.execute(
        "SELECT id, name, content, is_default, sig_type FROM user_signatures WHERE user_id = %s ORDER BY is_default DESC, created_at ASC",
        (user_id,),
    )
    return cur.fetchall()


def preview(text: str) -> str:
    """Short preview of content."""
    if not text:
        return "(empty)"
    total_br = len(_BR_RE.findall(text))
    first = (text.strip() or "")[:110].replace("\n", "\\n")
    return f"br={total_br} | {first}..."


def main():
    parser = argparse.ArgumentParser(description="Remove extra <br> from Kajal's signature")
    parser.add_argument("--apply", action="store_true", help="Write changes to DB (default is read-only)")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        user_id = find_kajal(cur)
        cur.execute("SELECT username, full_name FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        print(f"Kajal resolved: id={user_id}, username={u['username']}, full_name={u['full_name']}\n")

        # 1. user_signatures table
        sigs = fetch_signatures(cur, user_id)
        print(f"=== user_signatures ({len(sigs)} rows) ===")
        for s in sigs:
            old_content = s["content"] or ""
            new_content = to_standard_markdown(old_content)
            changed = new_content != old_content
            print(f"\n- Signature id={s['id']} name={s['name']!r} sig_type={s['sig_type']} is_default={s['is_default']}")
            print(f"  BEFORE: {preview(old_content)}")
            print(f"  AFTER:  {preview(new_content)}")
            if changed and args.apply:
                cur.execute(
                    "UPDATE user_signatures SET content = %s, updated_at = NOW() WHERE id = %s",
                    (new_content, s["id"]),
                )
                print("  -> UPDATED")
            elif changed:
                print("  -> would update (use --apply)")

        # 2. Legacy users.signature column
        cur.execute("SELECT signature FROM users WHERE id = %s", (user_id,))
        legacy = (cur.fetchone() or {}).get("signature") or ""
        print("\n=== legacy users.signature ===")
        if not legacy:
            print("  (empty - not stored here)")
        else:
            new_legacy = to_standard_markdown(legacy)
            print(f"  BEFORE: {preview(legacy)}")
            print(f"  AFTER:  {preview(new_legacy)}")
            if new_legacy != legacy and args.apply:
                cur.execute("UPDATE users SET signature = %s WHERE id = %s", (new_legacy, user_id))
                print("  -> UPDATED")
            elif new_legacy != legacy:
                print("  -> would update (use --apply)")

        if args.apply:
            conn.commit()
            print("\nChanges committed.")
        else:
            print("\n(Read-only - no changes made. Run with --apply to save.)")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
