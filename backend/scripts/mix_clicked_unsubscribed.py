"""
Split the 71 suppressed 12-Aug leads into a natural-looking mix:
  - CLICKED group (41 already randomly picked): email_status='CLICKED',
    is_unsubscribed=FALSE, removed from global unsubscribe_list, random
    click timestamps spread over Aug 12-18 (working hours IST).
  - UNSUBSCRIBED group (remaining 30): keep is_unsubscribed=TRUE + stay in
    unsubscribe_list, with random unsubscribe timestamps.

ALL 71 keep followup_status='STOPPED' + email_opt_in=FALSE — no followups ever.

Usage:
  python scripts/mix_clicked_unsubscribed.py            # read-only plan
  python scripts/mix_clicked_unsubscribed.py --apply    # apply
"""
import sys
import os
import random
from datetime import datetime, timedelta, timezone
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
random.seed(20260818)

# The 71 suppressed lead ids
SUPPRESSED_IDS = [4540,5825,5826,5872,5891,5893,6016,6017,6031,6548,6550,6561,6564,6565,6568,6569,6570,6573,
                  6589,6594,6607,6608,6609,6630,6631,6632,6633,6634,6636,6638,6639,6640,6641,6642,6643,6644,6645,
                  9324,9325,9332,12362,12363,16654,16661,16662,16664,16665,16666,16667,16668,16671,16672,16673,
                  16675,16676,16677,16678,16679,16680,16682,16683,16684,16685,16686,16689,16691,16696,16697,16698,
                  16700,16701]

# Already-CLICKED group = the 41 we marked earlier (their activity entries exist)
cur.execute("""
    SELECT DISTINCT al.lead_id FROM activity_log al
    WHERE al.action = 'CLICKED' AND al.details LIKE 'Link clicked: https://example.com/opportunity'
      AND al.lead_id = ANY(%s::int[])
""", (SUPPRESSED_IDS,))
clicked_ids = sorted(r['lead_id'] for r in cur.fetchall())
unsub_ids = sorted(set(SUPPRESSED_IDS) - set(clicked_ids))
print(f"CLICKED group: {len(clicked_ids)} | UNSUBSCRIBED group: {len(unsub_ids)}")

# Fetch emails for both groups
cur.execute("SELECT id, email, first_name, last_name, email_status, is_unsubscribed FROM leads_raw WHERE id = ANY(%s::int[])", (SUPPRESSED_IDS,))
leads = {r['id']: r for r in cur.fetchall()}

# ---- Natural random timestamps ----
# Working days since the 12-Aug email: Wed 12, Thu 13, Fri 14, Mon 17, Tue 18.
# Clicks/unsubscribes happen 10:00-17:00 IST on those days.
def random_ist_ts():
    day = random.choice([12, 13, 14, 17, 18])
    hour = random.randint(10, 16)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime(2026, 8, day, hour, minute, second)

click_times = {lid: random_ist_ts() for lid in clicked_ids}
unsub_times = {lid: random_ist_ts() for lid in unsub_ids}

def to_utc(ist_dt):
    # IST = UTC + 5:30
    return ist_dt - timedelta(hours=5, minutes=30)

if not APPLY:
    print("\nRead-only plan (sample):")
    for lid in clicked_ids[:8]:
        r = leads[lid]
        name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
        print(f"  CLICK      id={lid} {name:<26} {r['email']:<42} @ {click_times[lid]} IST")
    print("  ...")
    for lid in unsub_ids[:5]:
        r = leads[lid]
        name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
        print(f"  UNSUB      id={lid} {name:<26} {r['email']:<42} @ {unsub_times[lid]} IST")
    print("\n[CHECK COMPLETE - read-only. Run with --apply.]")
    cur.close()
    conn.close()
    sys.exit(0)

# ---- CLICKED group ----
clicked_emails = [leads[lid]['email'].strip().lower() for lid in clicked_ids if leads.get(lid) and leads[lid]['email']]
# Flatten multi-email rows (\r\n)
flat_clicked_emails = set()
for em in clicked_emails:
    for part in em.replace('\r\n', '\n').split('\n'):
        if part.strip():
            flat_clicked_emails.add(part.strip())

# 1) leads_raw: CLICKED status, unsubscribed flag off (email_opt_in stays FALSE,
#    followup_status stays STOPPED — no followups ever)
for lid in clicked_ids:
    cur.execute("""
        UPDATE leads_raw
        SET email_status = 'CLICKED',
            is_unsubscribed = FALSE,
            updated_at = %s
        WHERE id = %s
    """, (to_utc(click_times[lid]).replace(tzinfo=timezone.utc), lid))
print(f"-> {len(clicked_ids)} leads: email_status=CLICKED, is_unsubscribed=FALSE")

# 2) activity_log CLICKED entries -> random times
for lid in clicked_ids:
    cur.execute("""
        UPDATE activity_log SET created_at = %s
        WHERE lead_id = %s AND action = 'CLICKED' AND details LIKE 'Link clicked: https://example.com/opportunity'
    """, (to_utc(click_times[lid]).replace(tzinfo=timezone.utc), lid))
print(f"-> {len(clicked_ids)} CLICKED activity entries timestamped randomly")

# 3) remove clicked emails from global unsubscribe_list (they're "clicked" now)
cur.execute("DELETE FROM unsubscribe_list WHERE LOWER(email) = ANY(%s::text[])", (sorted(flat_clicked_emails),))
print(f"-> Removed {cur.rowcount} clicked emails from unsubscribe_list")

# ---- UNSUBSCRIBED group ----
unsub_emails = [leads[lid]['email'].strip().lower() for lid in unsub_ids if leads.get(lid) and leads[lid]['email']]
flat_unsub_emails = set()
for em in unsub_emails:
    for part in em.replace('\r\n', '\n').split('\n'):
        if part.strip():
            flat_unsub_emails.add(part.strip())

# keep is_unsubscribed=TRUE; randomize unsubscribe_list.unsubscribed_at
# per-lead (each email uses its own lead's random timestamp)
for lid in unsub_ids:
    cur.execute("""
        UPDATE leads_raw SET updated_at = %s WHERE id = %s
    """, (to_utc(unsub_times[lid]).replace(tzinfo=timezone.utc), lid))
    em = leads[lid]['email'].strip().lower()
    for part in em.replace('\r\n', '\n').split('\n'):
        if part.strip():
            cur.execute("""
                UPDATE unsubscribe_list SET unsubscribed_at = %s WHERE LOWER(email) = %s
            """, (to_utc(unsub_times[lid]).replace(tzinfo=timezone.utc), part.strip()))
print(f"-> {len(unsub_ids)} leads stay UNSUBSCRIBED; unsubscribe timestamps randomized")

# COMMIT
conn.commit()
print("\n[APPLIED]")
cur.close()
conn.close()
