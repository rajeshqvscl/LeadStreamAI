"""
Stop follow-ups for ALL replied leads in Yashika (user_id=4) and Palak (user_id=5) accounts.

A lead is considered "replied" if:
  - is_responded = TRUE, OR
  - email_status = 'REPLIED', OR
  - reply_intent IS NOT NULL

Applied when --apply is passed:
  - leads_raw.followup_status = 'STOPPED'
  - leads_raw.is_unsubscribed = TRUE
  - leads_raw.email_opt_in    = FALSE
  - unsubscribe_list          = insert all matched emails (prevents re-ingestion / future sends)
  - activity_log              = audit entries per lead

Usage:
  python scripts/stop_replied_followups.py            # read-only status report
  python scripts/stop_replied_followups.py --apply    # apply suppression
"""
import sys
import os
from collections import Counter
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
if not db_url:
    print("DATABASE_URL not found")
    sys.exit(1)
db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

APPLY = '--apply' in sys.argv
TARGET_USERS = {4: "Yashika Gupta (yashika.g)", 5: "Palak Jain (palak.j)"}

print("=" * 120)
print(f"MODE: {'APPLY SUPPRESSION' if APPLY else 'READ-ONLY CHECK'}")
print(f"SCOPE: Replied leads under user_id IN {sorted(TARGET_USERS)} ({', '.join(TARGET_USERS.values())})")
print("=" * 120)

for uid, uname in sorted(TARGET_USERS.items()):
    cur.execute("""
        SELECT id, first_name, last_name, email, followup_status, followup_stage,
               email_status, is_responded, reply_intent, is_unsubscribed, email_opt_in
        FROM leads_raw
        WHERE user_id = %s
          AND (is_responded = TRUE
               OR email_status = 'REPLIED'
               OR reply_intent IS NOT NULL)
        ORDER BY id
    """, (uid,))
    rows = cur.fetchall()
    print(f"\n[{uname} (user_id={uid})] replied leads: {len(rows)}")

    # Breakdown by reply intent for transparency
    intent_counts = Counter((r['reply_intent'] or 'UNCLASSIFIED') for r in rows)
    for k, v in intent_counts.most_common():
        print(f"    {k:<20} {v}")

    warm = [r for r in rows if (r['reply_intent'] or '') in ('INTERESTED', 'MEETING_REQUESTED')]
    if warm:
        print(f"    NOTE: {len(warm)} warm leads (INTERESTED/MEETING_REQUESTED) will also be STOPPED:")
        for r in warm:
            name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
            print(f"      ID {r['id']:>6} | {name:<24} | {r['email']:<42} | {r['reply_intent']} | {r['followup_status']}")

    if not APPLY:
        continue

    if not rows:
        continue

    ids = [r['id'] for r in rows]
    # Stop followups + mark unsubscribed
    cur.execute("""
        UPDATE leads_raw
        SET followup_status = 'STOPPED',
            is_unsubscribed = TRUE,
            email_opt_in = FALSE,
            updated_at = NOW()
        WHERE id = ANY(%s::int[])
    """, (ids,))
    print(f"    -> STOPPED followups for {cur.rowcount} leads.")

    # Add emails to global unsubscribe_list
    cur.execute("""
        SELECT DISTINCT LOWER(email) as email FROM leads_raw
        WHERE user_id = %s
          AND (is_responded = TRUE OR email_status = 'REPLIED' OR reply_intent IS NOT NULL)
          AND email IS NOT NULL AND email != ''
    """, (uid,))
    emails = [r['email'] for r in cur.fetchall()]
    inserted = 0
    for em in emails:
        try:
            cur.execute("""
                INSERT INTO unsubscribe_list (email, reason, source)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING
            """, (em, f"Replied lead - followups stopped ({uname})", "manual_suppression"))
            inserted += cur.rowcount
        except Exception as e:
            print(f"      ! failed to insert {em}: {e}")
    print(f"    -> Added {inserted} unique emails to unsubscribe_list (total tracked: {len(emails)}).")

    # COMMIT the core suppression FIRST so a cosmetic audit failure can never roll it back
    conn.commit()

    # Audit log (separate transaction - failures here don't undo the suppression)
    try:
        for lid in ids:
            cur.execute("""
                INSERT INTO activity_log (lead_id, action, details, performed_by, user_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (lid, "FOLLOWUP_STOPPED", f"Manual suppression - replied lead, followups stopped ({uname})", "admin", uid))
        conn.commit()
    except Exception as audit_err:
        # Reset the connection so the next user iteration still works
        conn.rollback()
        print(f"    ! Audit log insert failed (suppression already committed): {audit_err}")

print("\n" + ("[SUPPRESSION APPLIED]" if APPLY else "[CHECK COMPLETE - read-only. Run with --apply to suppress.]"))
cur.close()
conn.close()
