"""
One-time backfill: fix Yashika's (user_id=4) investor/company leads whose
first_name is purely numeric or contains no letters (so the review queue shows a
number instead of a name).

Recomputes first_name/last_name by re-reading the lead's stored raw_payload
(the original company-registry row), picking the FIRST candidate field that looks
like a real person name (has letters, not a URL, not numeric). This recovers the
correct contact names (e.g. Aditya, Ganesh, Krupa, Manoj, Meyyappanan, Shivkumar,
Suresh) that were being shadowed by a numeric 'name' field. Falls back to the
email local-part only if no alphabetic name exists anywhere in the payload.

Run:  python backend/scripts/fix_yashika_numeric_names.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
from app.database import get_db_connection


def extract_name_from_payload(raw_payload):
    """Return (first_name, last_name) from a company-registry row, or ('', '')."""
    if not raw_payload:
        return ("", "")
    if isinstance(raw_payload, str):
        try:
            raw_payload = json.loads(raw_payload)
        except Exception:
            return ("", "")
    if not isinstance(raw_payload, dict):
        return ("", "")
    norm = {str(k).lower().replace(" ", "").replace("-", "").replace("_", ""): v for k, v in raw_payload.items() if v}
    candidates = [
        norm.get("name"), norm.get("fullname"),
        norm.get("leadname"), norm.get("contactname"), norm.get("contact"),
        norm.get("investor"), norm.get("person"), norm.get("personname"),
        f"{norm.get('firstname', '')} {norm.get('lastname', '')}".strip(),
    ]
    for cand in candidates:
        cand = (cand or "").strip()
        if not cand:
            continue
        if "http://" in cand.lower() or "https://" in cand.lower() or "linkedin.com" in cand.lower():
            continue
        if not any(ch.isalpha() for ch in cand):
            continue
        parts = cand.split(" ", 1)
        return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")
    return ("", "")


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute(
        """
        SELECT id, first_name, last_name, email, company_name, raw_payload
        FROM leads_raw
        WHERE user_id = 4
          AND email IS NOT NULL
          AND (first_name IS NULL OR first_name = '' OR NOT (first_name ~ '[A-Za-z]'))
        """
    )
    rows = cur.fetchall()
    print(f"Found {len(rows)} Yashika leads with non-alphabetic first_name")

    updated = 0
    for r in rows:
        f_name, l_name = extract_name_from_payload(r["raw_payload"])
        if not f_name:
            # Fall back to email local-part (mirrors company-generation behaviour)
            local = r["email"].split("@")[0]
            name = local.replace(".", " ").replace("_", " ").replace("-", " ").title()
            parts = name.split(" ", 1)
            f_name = parts[0]
            l_name = parts[1] if len(parts) > 1 else ""
        cur.execute(
            "UPDATE leads_raw SET first_name = %s, last_name = %s WHERE id = %s",
            (f_name, l_name or "", r["id"]),
        )
        updated += 1
        print(f"  id={r['id']}  ->  '{f_name} {l_name}'.strip()  (was '{r['first_name']}')")

    conn.commit()
    cur.close()
    conn.close()
    print(f"Updated {updated} leads.")


if __name__ == "__main__":
    main()
