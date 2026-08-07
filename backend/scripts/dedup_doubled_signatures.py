"""
One-off backfill: de-duplicate signature lines that were baked TWICE into
stored email_drafts by the markdown_to_html 'Smart Signature Styling'
double-append bug.

The buggy code appended already-HTML signature lines (names in <strong>,
[Website](url) | [LinkedIn](url) links) both inside the branch (line + "<br>")
AND via the shared append at the bottom of the loop, producing:

    <strong><em>Palak Jain</em></strong><br><strong><em>Palak Jain</em></strong>

in the stored/rendered draft (name and link lines doubled, plain-text lines not).

This script reverses the exact bug pattern: any identical HTML fragment
immediately followed by "<br>" + the SAME fragment gets reduced to one copy.

Dry-run by default; pass --apply to write.

Usage:
    python scripts/dedup_doubled_signatures.py            # dry-run
    python scripts/dedup_doubled_signatures.py --apply    # write
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "app" / ".env")

from app.database import get_db_connection
import psycopg2.extras

# An HTML fragment (opening tag -> closing tag), possibly containing nested
# tags and inline text (e.g. <strong><em>Palak Jain</em></strong> or
# <a href="...">Website</a> | <a href="...">LinkedIn</a>).
_LINE = r'<[^>]+>(?:[^<>]|<[^>]+>)*</[^>]+>'
# The exact bug output: LINE<br>LINE  ->  LINE
_DUP_RE = re.compile(r'(' + _LINE + r')<br>\1')
# Variant with self-closing <br/> (harmless safety net)
_BRSLASH_DUP_RE = re.compile(r'(' + _LINE + r')<br/>\1')
# display:block <img> lines were doubled WITHOUT a <br> between the copies
# (buggy branch appended `line` twice, producing adjacent <img/><img/>).
_IMG_DUP_RE = re.compile(r'(<img[^>]*/>)\1')


def dedup(html: str) -> str:
    """Remove the LINE<br>LINE (and adjacent <img/><img/>) doubling produced by
    the buggy renderer."""
    if not html:
        return html
    # The bug is single-level; one pass removes it.
    new = _DUP_RE.sub(r'\1', html)
    new = _BRSLASH_DUP_RE.sub(r'\1', new)
    new = _IMG_DUP_RE.sub(r'\1', new)
    return new


def main():
    apply_changes = "--apply" in sys.argv
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Prefilter in SQL — only drafts whose rendered signature has a doubled
    # HTML line (name in <strong> or [Website]|[LinkedIn] links in <a>) carry
    # the bug, so we avoid regex-scanning all 10k+ drafts.
    cur.execute(
        "SELECT id, user_id, email_status, email_draft FROM leads_raw "
        "WHERE email_draft IS NOT NULL "
        "AND (email_draft LIKE '%</strong><br><strong%' OR email_draft LIKE '%</a><br><a %' "
        "OR email_draft LIKE '%</span><br><span%' OR email_draft LIKE '%</em></strong><br><strong%') "
        "ORDER BY id"
    )
    rows = cur.fetchall()

    changed = []
    for r in rows:
        orig = r["email_draft"] or ""
        fixed = dedup(orig)
        if fixed != orig:
            changed.append((r["id"], r["user_id"], r["email_status"], orig, fixed))

    print(f"Scanned {len(rows)} drafts. {len(changed)} have doubled signature lines.\n")

    for lead_id, uid, status, orig, fixed in changed[:40]:
        print(f"--- lead {lead_id} (user {uid}, {status}) ---")
        # Show a compact before/after of the first changed region
        m = _DUP_RE.search(orig)
        if m:
            s = max(0, m.start() - 120)
            e = min(len(orig), m.end() + 120)
            print("BEFORE:", orig[s:e])
            m2 = _DUP_RE.search(fixed)
            s2 = max(0, m2.start() - 120) if m2 else max(0, s)
            e2 = min(len(fixed), m2.end() + 120) if m2 else min(len(fixed), e)
            print("AFTER :", fixed[s2:e2])
        print()

    if len(changed) > 40:
        print(f"... and {len(changed) - 40} more.\n")

    if not apply_changes:
        print(f"DRY-RUN: {len(changed)} drafts would be updated. Re-run with --apply to write.")
        conn.close()
        return

    for lead_id, uid, status, orig, fixed in changed:
        cur.execute("UPDATE leads_raw SET email_draft = %s WHERE id = %s", (fixed, lead_id))
    conn.commit()
    print(f"APPLIED: updated {len(changed)} drafts.")
    conn.close()


if __name__ == "__main__":
    main()
