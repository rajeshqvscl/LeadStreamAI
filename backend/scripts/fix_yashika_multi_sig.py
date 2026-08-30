"""
One-time cleanup: collapse Yashika's (user_id=4) stored email_drafts that have
multiple signatures down to exactly ONE.

Root cause: inject_signature() was non-idempotent (its strip regex missed the
real saved-signature '<div border-top>' block), so every re-render stacked another
copy. This re-strips all signature blocks, then re-injects a single fresh one
(using the sender's current profile) — exactly what the send path now does.

Dry-run by default; pass --apply to write.
Run:
    python backend/scripts/fix_yashika_multi_sig.py
    python backend/scripts/fix_yashika_multi_sig.py --apply
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "app" / ".env")

from app.database import get_db_connection
import psycopg2.extras
from app.api.drafts import inject_signature, get_sender_profile


def strip_signature_blocks(html: str) -> str:
    html = re.sub(r'<div\s+style="color:\s*#666666;.*?</div>\s*$', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<div\s+style="[^"]*border-top:\s*1px\s+solid\s+#f0f0f0[^"]*">.*?</div>\s*', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<div\s+style="color:\s*#000000;.*?</div>\s*', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'(?m)^\s*(?:--|—)\s*$', '', html)
    return html.strip()


def main():
    apply_changes = "--apply" in sys.argv
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Only the drafts shown in the Review Queue can display multiple signatures;
    # already-sent ones render fine, so we scope the cleanup to in-flight statuses
    # across all users (the review queue is shared / admin-viewable).
    cur.execute(
        "SELECT id, user_id, email_status, email_draft FROM leads_raw "
        "WHERE email_draft IS NOT NULL "
        "AND email_status IN ('PENDING_APPROVAL','SCHEDULED','DRAFT','pending')"
    )
    rows = cur.fetchall()
    print(f"Scanned {len(rows)} in-flight drafts.\n", flush=True)

    # Cache sender profiles per user to avoid a DB round-trip per lead
    _profiles = {}

    def _profile_for(uid):
        key = str(uid)
        if key not in _profiles:
            _profiles[key] = get_sender_profile(key)
        return _profiles[key]

    changed = 0
    for r in rows:
        content = r["email_draft"] or ""
        # Split "Subject: ..." prefix if present
        if content.lstrip().lower().startswith("subject:"):
            subject_line, _, body = content.partition("\n\n")
            subject = subject_line.split(":", 1)[1].strip() if ":" in subject_line else ""
        else:
            subject, body = "", content

        # Count existing signature blocks (pre-fix) to decide if cleanup needed
        n_sig = len(re.findall(r'border-top:\s*1px\s+solid\s+#f0f0f0', body, flags=re.IGNORECASE))
        if n_sig <= 1:
            continue

        cleaned_body = strip_signature_blocks(body)
        new_body = inject_signature(cleaned_body, _profile_for(r["user_id"]), r["id"])
        new_content = f"Subject: {subject}\n\n{new_body}" if subject else new_body

        if apply_changes:
            cur.execute("UPDATE leads_raw SET email_draft = %s WHERE id = %s", (new_content, r["id"]))
        changed += 1
        print(f"  id={r['id']} ({r['email_status']}): {n_sig} sig blocks -> 1")

    if apply_changes:
        conn.commit()
        print(f"\nAPPLIED: collapsed {changed} drafts to a single signature.")
    else:
        print(f"DRY-RUN: {changed} drafts have multiple signatures. Re-run with --apply to write.")
    conn.close()


if __name__ == "__main__":
    main()
