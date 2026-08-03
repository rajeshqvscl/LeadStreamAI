"""
Migration: Change email/followup draft fonts to `sans-serif` for ALL users
EXCEPT Ayush (user 2).

Rewrites baked-in `font-family` declarations inside stored HTML drafts using
bulk SQL REGEXP_REPLACE (fast even for thousands of rows):
  - leads_raw.email_draft / followup_draft  (WHERE user_id IS DISTINCT FROM 2)
  - prompts content/followup_1/2/3          (owner is NOT ayush)

Ayush (user 2) is deliberately NOT touched — his drafts keep `Arial, sans-serif`.

Run from backend/:
    python scripts/update_gmail_sans_font.py            # dry-run (read-only preview)
    python scripts/update_gmail_sans_font.py --apply    # actually apply changes
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env"]:
    if os.path.exists(env_loc):
        from dotenv import load_dotenv
        load_dotenv(env_loc)
        break

sys.path.append(os.getcwd())
from app.database import get_db_connection

EXCLUDED_USER_IDS = (2,)              # ayush — never touched
EXCLUDED_USERNAME = "ayush"           # prompts owned by ayush — never touched
SANS_SERIF = "sans-serif"

# Matches `font-family: X` or `font-family:X` up to the `;` / `"` / `'` boundary.
# Uses `[ ]*` for optional spaces — backslash-free, safe in SQL and Python alike.
SQL_REPLACE_PATTERN = "font-family[ ]*:[ ]*[^;\"']+"
SQL_REPLACE_WITH = "font-family: " + SANS_SERIF


def main():
    apply_changes = "--apply" in sys.argv
    conn = get_db_connection()
    cur = conn.cursor()

    print("=== SANS-SERIF FONT MIGRATION (everyone except Ayush) ===")
    print("Mode: " + ("APPLY" if apply_changes else "DRY-RUN"))
    print()

    # ── 1. leads_raw email_draft / followup_draft ──
    for col in ("email_draft", "followup_draft"):
        cur.execute(
            "SELECT COUNT(*) AS c FROM leads_raw WHERE user_id IS DISTINCT FROM %s AND {0} ~ 'font-family'".format(col),
            (EXCLUDED_USER_IDS[0],),
        )
        before = cur.fetchone()["c"]
        if apply_changes and before:
            cur.execute(
                "UPDATE leads_raw SET {0} = REGEXP_REPLACE({0}, %s, %s, 'g'), updated_at = NOW() "
                "WHERE user_id IS DISTINCT FROM %s AND {0} ~ 'font-family'".format(col),
                (SQL_REPLACE_PATTERN, SQL_REPLACE_WITH, EXCLUDED_USER_IDS[0]),
            )
            conn.commit()
        print("leads_raw.{0}: {1} row(s) {2}".format(col, before, "updated" if apply_changes else "would update"))

    # ── 2. prompts content / followup_1 / followup_2 / followup_3 ──
    # Only prompts NOT owned by ayush (by owner_username AND by name prefix).
    ayush_name_like = "ayush%"
    for pcol in ("content", "followup_1", "followup_2", "followup_3"):
        cur.execute(
            "SELECT COUNT(*) AS c FROM prompts "
            "WHERE LOWER(COALESCE(owner_username, '')) <> %s "
            "AND LOWER(name) NOT LIKE %s AND {0} ~ 'font-family'".format(pcol),
            (EXCLUDED_USERNAME, ayush_name_like),
        )
        before = cur.fetchone()["c"]
        if apply_changes and before:
            cur.execute(
                "UPDATE prompts SET {0} = REGEXP_REPLACE({0}, %s, %s, 'g') "
                "WHERE LOWER(COALESCE(owner_username, '')) <> %s "
                "AND LOWER(name) NOT LIKE %s AND {0} ~ 'font-family'".format(pcol),
                (SQL_REPLACE_PATTERN, SQL_REPLACE_WITH, EXCLUDED_USERNAME, ayush_name_like),
            )
            conn.commit()
        print("prompts.{0}: {1} row(s) {2}".format(pcol, before, "updated" if apply_changes else "would update"))

    # ── 3. Verify: how many non-ayush drafts use the target font vs another font ──
    pattern = "font-family[ ]*:[ ]*[^;\"]+"
    new_pattern = "font-family[ ]*:[ ]*" + re.escape(SANS_SERIF)
    cur.execute(
        "SELECT COUNT(*) AS c FROM leads_raw WHERE user_id IS DISTINCT FROM %s AND email_draft ~ %s AND email_draft !~ %s",
        (EXCLUDED_USER_IDS[0], pattern, new_pattern),
    )
    still_old = cur.fetchone()["c"]
    cur.execute(
        "SELECT COUNT(*) AS c FROM leads_raw WHERE user_id IS DISTINCT FROM %s AND email_draft ~ %s",
        (EXCLUDED_USER_IDS[0], new_pattern),
    )
    with_new = cur.fetchone()["c"]
    print()
    print("Verify: {} non-ayush drafts now use '{}'; {} still show an old font.".format(with_new, SANS_SERIF, still_old))

    # ── 4. Safety: confirm Ayush (user 2) untouched in this run ──
    cur.execute(
        "SELECT COUNT(*) AS c FROM leads_raw WHERE user_id = 2 AND email_draft ~ 'font-family'"
    )
    ayush = cur.fetchone()["c"]
    print("Sanity: Ayush (user 2) leads with font-family left untouched: {}".format(ayush))

    cur.close()
    conn.close()

    if not apply_changes:
        print()
        print("Dry-run complete — no changes made. Re-run with --apply to execute.")
    else:
        print()
        print("Migration applied.")


if __name__ == "__main__":
    main()
