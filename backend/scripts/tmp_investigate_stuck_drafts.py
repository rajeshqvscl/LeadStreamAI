"""Investigate: drafted (APPROVED/PENDING_APPROVAL) leads that remain unsent — why?"""
import sys
import os
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env", "../../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

import psycopg2
from psycopg2.extras import RealDictCursor
from collections import Counter

db_url = os.getenv('DATABASE_URL')
db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# All leads still in APPROVED / PENDING_APPROVAL (drafted but unsent), per user
cur.execute("""
    SELECT l.id, l.user_id, u.full_name, l.email, l.email_status, l.followup_status,
           l.is_responded, l.replied_at, l.reply_intent, l.is_unsubscribed, l.email_opt_in,
           l.email_draft IS NOT NULL AS has_draft,
           l.draft_template_used,
           EXISTS(SELECT 1 FROM unsubscribe_list ul WHERE ul.email = l.email) AS in_unsub_list,
           l.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS created_ist,
           l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' AS updated_ist
    FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id
    WHERE l.email_status IN ('APPROVED', 'PENDING_APPROVAL')
    ORDER BY l.user_id, l.updated_at DESC
""")
rows = cur.fetchall()
print(f"Total drafted-but-unsent leads (APPROVED/PENDING_APPROVAL): {len(rows)}")

by_user = Counter()
for r in rows:
    by_user[r['user_id']] += 1
print(f"By user: {dict(sorted(by_user.items(), key=lambda x: str(x[0])))}")

# Guard breakdown — which safety guard blocks each?
guards = Counter()
for r in rows:
    reasons = []
    if r['is_responded'] or r['replied_at'] is not None:
        reasons.append('replied')
    if r['reply_intent']:
        reasons.append(f"reply_intent={r['reply_intent']}")
    if r['is_unsubscribed']:
        reasons.append('is_unsubscribed')
    if r['email_opt_in'] is False:
        reasons.append('email_opt_in=False')
    if r['in_unsub_list']:
        reasons.append('in_unsub_list')
    if not r['has_draft']:
        reasons.append('NO_DRAFT')
    guards['+'.join(reasons) if reasons else 'CLEAN (no guard blocks)'] += 1

print("\nWhy they'd be skipped by send-approved-batch guards:")
for k, v in guards.most_common():
    print(f"  {v:>4}  {k}")

# Show a sample of CLEAN ones (should be sendable — why are they stuck?)
print("\n=== CLEAN leads (no guard blocks, should send but stuck) — sample ===")
clean = [r for r in rows if not (r['is_responded'] or r['replied_at'] is not None or r['reply_intent']
                                 or r['is_unsubscribed'] or r['email_opt_in'] is False or r['in_unsub_list'])
         and r['has_draft']]
print(f"Total CLEAN but unsent: {len(clean)}")
for r in clean[:15]:
    name = r['full_name'] or '?'
    print(f"  id={r['id']} user={r['user_id']}({name:<14}) {r['email']:<42} status={r['email_status']} tpl={r['draft_template_used']!r} updated={r['updated_ist']}")

# For clean ones — was there an EMAIL_SENT activity? (sent but status not updated?)
if clean:
    ids = [r['id'] for r in clean]
    cur.execute("""
        SELECT al.lead_id, COUNT(*) AS c FROM activity_log al
        WHERE al.lead_id = ANY(%s::int[]) AND al.action = 'EMAIL_SENT'
        GROUP BY al.lead_id
    """, (ids,))
    sent_log = {r['lead_id']: r['c'] for r in cur.fetchall()}
    have_sent_log = sum(1 for i in ids if sent_log.get(i))
    print(f"\nOf {len(ids)} clean leads, {have_sent_log} already have an EMAIL_SENT activity entry (sent but status stuck?)")

cur.close()
conn.close()
print("\nDONE")
