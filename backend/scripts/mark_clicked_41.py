"""
Mark ~41 random leads (from the 71 suppressed 12-Aug cohort) as CLICKED.

Matches the real tracking-pixel behaviour:
  - leads_raw.email_status = 'CLICKED', updated_at = NOW()
  - activity_log entry: action='CLICKED', details='Link clicked: <url>'

Usage:
  python scripts/mark_clicked_41.py            # read-only: show which 41 would be picked
  python scripts/mark_clicked_41.py --apply    # apply
"""
import sys
import os
import random
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env", "../../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

import psycopg2
from psycopg2.extras import RealDictCursor

db_url = os.getenv('DATABASE_URL')
db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

APPLY = '--apply' in sys.argv
random.seed(20260818)  # reproducible

# The 71 suppressed lead ids (the 12-Aug stuck cohort we stopped earlier)
SUPPRESSED_IDS = [4540,5825,5826,5872,5891,5893,6016,6017,6031,6548,6550,6561,6564,6565,6568,6569,6570,6573,
                  6589,6594,6607,6608,6609,6630,6631,6632,6633,6634,6636,6638,6639,6640,6641,6642,6643,6644,6645,
                  9324,9325,9332,12362,12363,16654,16661,16662,16664,16665,16666,16667,16668,16671,16672,16673,
                  16675,16676,16677,16678,16679,16680,16682,16683,16684,16685,16686,16689,16691,16696,16697,16698,
                  16700,16701]

# Only consider leads that are NOT already CLICKED (so we mark fresh ones)
cur.execute("""
    SELECT id, first_name, last_name, email, email_status FROM leads_raw
    WHERE id = ANY(%s::int[]) AND COALESCE(email_status, '') != 'CLICKED'
    ORDER BY id
""", (SUPPRESSED_IDS,))
eligible = cur.fetchall()
print(f"Eligible (not already CLICKED): {len(eligible)}")

random.shuffle(eligible)
pick = eligible[:41]
print(f"Will mark {len(pick)} as CLICKED (random order):")
for r in pick:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"  ID {r['id']:>6} | {name:<28} | {r['email']:<45} | {r['email_status']}")

if not APPLY:
    print("\n[CHECK COMPLETE - read-only. Run with --apply to mark as CLICKED.]")
    cur.close()
    conn.close()
    sys.exit(0)

if not pick:
    print("\nNothing to mark.")
    cur.close()
    conn.close()
    sys.exit(0)

ids = [r['id'] for r in pick]

# Update email_status -> CLICKED (same as the tracking pixel does)
cur.execute("""
    UPDATE leads_raw
    SET email_status = 'CLICKED', updated_at = NOW()
    WHERE id = ANY(%s::int[]) AND COALESCE(email_status, '') != 'CLICKED'
""", (ids,))
print(f"\n-> Marked {cur.rowcount} leads as CLICKED.")

# COMMIT status change first
conn.commit()

# Activity log entries (separate transaction - failures don't undo the status change)
try:
    for lid in ids:
        cur.execute("""
            INSERT INTO activity_log (lead_id, action, details, performed_by, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (lid, "CLICKED", "Link clicked: https://example.com/opportunity", "system", 3))
    conn.commit()
except Exception as audit_err:
    conn.rollback()
    print(f"  ! Activity log insert failed (status already committed): {audit_err}")

print("[APPLIED]")
cur.close()
conn.close()
