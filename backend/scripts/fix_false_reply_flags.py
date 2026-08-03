"""
Fix false 'is_responded' flags.

Root cause (fixed in gmail.py): the bounce handler used to set
`is_responded = TRUE` when an email bounced. A bounced email is NOT a reply,
so ~600 leads ended up flagged as "replied" while their email_status is
'BOUNCED' (reply_intent empty) — polluting every Replies filter/dashboard.

This script resets the flag for the clear false positives:
  is_responded = TRUE AND email_status = 'BOUNCED' AND reply_intent IS NULL/empty

Leads with email_status='BOUNCED' but a non-empty reply_intent are NOT touched
(they replied before the bounce was detected).

Usage:
  python scripts/fix_false_reply_flags.py            # dry run (no changes)
  python scripts/fix_false_reply_flags.py --apply    # apply changes
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
for env_loc in ['app/.env', 'backend/app/.env', '../backend/app/.env']:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break
sys.path.append(os.getcwd())
from app.database import get_db_connection

APPLY = '--apply' in sys.argv

conn = get_db_connection()
cur = conn.cursor()

# Affected: bounced + flagged responded + never got an intent (clear false positive)
cur.execute("""
    SELECT l.id, l.email, u.username, l.email_status, l.is_responded, l.reply_intent
    FROM leads_raw l
    LEFT JOIN users u ON l.user_id = u.id
    WHERE l.is_responded = TRUE
      AND l.email_status ILIKE 'BOUNCED'
      AND (l.reply_intent IS NULL OR l.reply_intent = '')
    ORDER BY u.username
""")
rows = cur.fetchall()
print(f"False-flag leads to fix (bounced + is_responded + no intent): {len(rows)}")
from collections import Counter
by_owner = Counter(r['username'] for r in rows)
for o, c in by_owner.most_common():
    print(f"  {str(o):12s} | {c}")

# Sanity: bounced + flagged but WITH an intent — NOT touched (genuinely replied)
cur.execute("""
    SELECT COUNT(*) AS c FROM leads_raw
    WHERE is_responded = TRUE AND email_status ILIKE 'BOUNCED'
      AND (reply_intent IS NOT NULL AND reply_intent <> '')
""")
print(f"\nBounced+responded WITH intent (kept, genuinely replied): {cur.fetchone()['c']}")

# Sanity: real replies that must remain flagged
cur.execute("""
    SELECT COUNT(*) AS c FROM leads_raw
    WHERE is_responded = TRUE AND email_status ILIKE 'REPLIED'
""")
print(f"Real REPLIED leads that stay flagged: {cur.fetchone()['c']}")

if not APPLY:
    print("\n[DRY RUN] No changes made. Re-run with --apply to fix.")
else:
    ids = [r['id'] for r in rows]
    if not ids:
        print("\nNothing to fix.")
    else:
        audit_file = os.path.join(os.getcwd(), 'scripts', 'fix_false_reply_flags_audit.csv')
        with open(audit_file, 'w', encoding='utf-8') as f:
            f.write("id,email,owner\n")
            for r in rows:
                f.write(f"{r['id']},{r['email']},{r['username']}\n")
        cur.execute("""
            UPDATE leads_raw
            SET is_responded = FALSE, updated_at = updated_at
            WHERE id = ANY(%s)
        """, (ids,))
        conn.commit()
        print(f"\n[APPLIED] Reset is_responded=FALSE on {len(ids)} leads. Audit log: {audit_file}")

cur.close()
conn.close()
print("DONE")
