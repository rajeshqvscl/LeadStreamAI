"""
Backfill `leads_raw.replied_at` from real reply evidence.

Evidence sources (strongest first):
  1. REPLY_DETECTED activity-log events (feature added Aug 3, 2026) — use the
     event's created_at.
  2. FOLLOWUP_STOPPED events whose details read
     'Reply received from <name> (<email>) at same company — auto-stopped' —
     the email inside the details is the ACTUAL replier. Use the earliest such
     event's created_at for that replier email (this is the only historical
     evidence for June/July replies, since REPLY_DETECTED logging didn't exist).

Leads that stay `replied_at = NULL` are the "unsourced" flags (no event
evidence) — they are excluded from monthly reply counts by the report queries.

Idempotent: only sets replied_at when it is currently NULL (COALESCE-style).
Run from backend/:  python scripts/backfill_replied_at.py
"""
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, '.')
load_dotenv(dotenv_path=Path("app/main.py").resolve().parent / ".env")

from app.database import get_db_connection

EMAIL_RE = re.compile(r"\(([\w.+-]+@[\w.-]+)\)")

conn = get_db_connection()
cur = conn.cursor()

# ── Source 1: REPLY_DETECTED events → lead_id → earliest event time ──
cur.execute("""
    SELECT lead_id, MIN(created_at) AS d
    FROM activity_log
    WHERE action = 'REPLY_DETECTED'
    GROUP BY 1
""")
reply_detected = {r["lead_id"]: r["d"] for r in cur.fetchall()}
print(f"REPLY_DETECTED events (lead_id -> earliest date): {len(reply_detected)}")

# ── Source 2: auto-stop 'Reply received from X (email)...' → email → earliest event time ──
cur.execute("""
    SELECT details, created_at
    FROM activity_log
    WHERE action = 'FOLLOWUP_STOPPED'
      AND details ILIKE 'Reply received from%'
    ORDER BY created_at
""")
replier_dates = {}
for r in cur.fetchall():
    m = EMAIL_RE.search(r["details"] or "")
    if m:
        em = m.group(1).lower()
        if em not in replier_dates:
            replier_dates[em] = r["created_at"]
print(f"Auto-stop replier emails -> earliest date: {len(replier_dates)}")

# ── Apply ──
updated = 0
skipped = 0
errors = 0

# 1. By REPLY_DETECTED lead_id
for lead_id, ts in reply_detected.items():
    try:
        cur.execute(
            "UPDATE leads_raw SET replied_at = COALESCE(replied_at, %s) WHERE id = %s",
            (ts, lead_id),
        )
        updated += cur.rowcount
    except Exception as e:
        errors += 1
        print(f"  ERROR lead {lead_id}: {e}")

# 2. By replier email (only leads that are flagged replied)
for em, ts in replier_dates.items():
    try:
        cur.execute(
            """
            UPDATE leads_raw SET replied_at = COALESCE(replied_at, %s)
            WHERE LOWER(email) = LOWER(%s) AND is_responded = TRUE
            """,
            (ts, em),
        )
        updated += cur.rowcount
    except Exception as e:
        errors += 1
        print(f"  ERROR email {em}: {e}")

conn.commit()

# ── Summary ──
cur.execute("SELECT COUNT(*) AS c FROM leads_raw WHERE is_responded = TRUE")
total_flagged = cur.fetchone()["c"]
cur.execute("SELECT COUNT(*) AS c FROM leads_raw WHERE is_responded = TRUE AND replied_at IS NOT NULL")
with_date = cur.fetchone()["c"]
cur.execute("SELECT COUNT(*) AS c FROM leads_raw WHERE is_responded = TRUE AND replied_at IS NULL")
no_date = cur.fetchone()["c"]

print()
print("=" * 60)
print("SUMMARY")
print(f"  rows updated:              {updated}")
print(f"  errors:                    {errors}")
print(f"  is_responded total:        {total_flagged}")
print(f"  with replied_at (verified): {with_date}")
print(f"  without replied_at (unsourced): {no_date}")
print()

# Monthly distribution of verified
cur.execute("""
    SELECT EXTRACT(YEAR FROM replied_at)::int AS y,
           EXTRACT(MONTH FROM replied_at)::int AS m,
           COUNT(*) AS c
    FROM leads_raw
    WHERE replied_at IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1, 2
""")
print("Verified replied_at monthly distribution:")
for r in cur.fetchall():
    print(f"  {r['y']}-{r['m']:02d}: {r['c']}")

cur.close()
conn.close()
