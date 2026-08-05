"""
Remove SIG_START/SIG_END marker blocks from all prompt templates and stored
email drafts where they appear.

Template contents and generated drafts carry a dead signature block wrapped in
SIG_START...SIG_END. The block is never used: markdown_to_html() strips it at
render time and the real signature is injected separately by inject_signature().
Removing it cleans the Prompts page and the EditEmail WYSIWYG editor, which
otherwise show the literal SIG_START / SIG_END text.

Transformation is done server-side with regexp_replace (fast even for tens of
thousands of rows). Dry-run reports counts + row ids; --apply writes.

Run from backend/ directory:
    python scripts/remove_sig_markers.py            # read-only: show what would change
    python scripts/remove_sig_markers.py --apply    # apply
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
import psycopg2.extras

# Postgres ARE regex. Non-greedy .*? is supported. Trailing part also eats the
# literal backslash-n style line breaks that some older drafts use.
BLOCK = r"[ \t]*SIG_START.*?SIG_END[ \t]*(?:\r?\n|\\n)?"
# Unclosed block (SIG_START with no SIG_END): tempered dot removes everything to
# the end of the string only when no SIG_END follows.
UNCLOSED = r"[ \t]*SIG_START(?:(?!SIG_END).)*$"
COLLAPSE = r"\n{3,}"
TRAIL = r"(?:\r?\n|\\n)+$"
COLLAPSE_REPL = "\n\n"  # real newlines (Postgres \n in replacement means backref!)


def build_expr(column: str) -> str:
    """SQL expression that applies the SIG-block removal to a column."""
    return (
        f"regexp_replace(regexp_replace(regexp_replace(regexp_replace("
        f"{column}, %s, '', 'gs'), %s, '', 's'), %s, %s, 'g'), %s, '', 'g')"
    )


def main():
    parser = argparse.ArgumentParser(description="Remove SIG_START/SIG_END blocks")
    parser.add_argument("--apply", action="store_true", help="Write changes to DB (default is read-only)")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        targets = []  # (table, column)
        for table, column in [("leads_raw", "email_draft"), ("prompts", "content")]:
            cur.execute(
                f"SELECT count(*) AS n FROM {table} WHERE {column} ILIKE '%SIG_START%'"
            )
            n = cur.fetchone()["n"] or 0
            if n:
                targets.append((table, column, n))

        if not targets:
            print("No SIG_START found anywhere. Nothing to do.")
            return

        print("=== Rows containing SIG_START ===")
        for table, column, n in targets:
            print(f"  {table}.{column}: {n} row(s)")

        if not args.apply:
            # Preview: show a few row ids per target
            for table, column, _n in targets:
                cur.execute(
                    f"SELECT id FROM {table} WHERE {column} ILIKE '%SIG_START%' ORDER BY id LIMIT 5"
                )
                ids = [r["id"] for r in cur.fetchall()]
                print(f"\n  {table}.{column} sample ids: {ids}")
            print("\n(Read-only - no changes made. Run with --apply to save.)")
            return

        for table, column, _n in targets:
            cur.execute(
                f"UPDATE {table} SET {column} = {build_expr(column)} "
                f"WHERE {column} ILIKE %s",
                (BLOCK, UNCLOSED, COLLAPSE, COLLAPSE_REPL, TRAIL, "%SIG_START%"),
            )
            print(f"  {table}.{column}: {cur.rowcount} row(s) updated")

        conn.commit()
        print("Changes committed.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
