"""Close followups for Kajal's ACTIVE leads up to 30 July 2026 (leads kept)."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv('app/.env')
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import Counter

url = os.getenv('DATABASE_URL', '').strip().strip(chr(39)).strip(chr(34)).replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# 1. Find Kajal's user id
cur.execute("SELECT id, username FROM users WHERE username ILIKE '%kajal%'")
kajal_users = cur.fetchall()
print("Kajal users:", [(u['id'], u['username']) for u in kajal_users])
kajal_ids = [u['id'] for u in kajal_users]

# 2. Identify targets: ACTIVE leads, last_outreach <= 2026-07-30
cur.execute("""
    SELECT l.id, l.followup_stage, l.followup_status, l.last_outreach_at, l.email_status
    FROM leads_raw l
    WHERE l.user_id = ANY(%s)
      AND l.followup_status = 'ACTIVE'
      AND l.last_outreach_at IS NOT NULL
      AND l.last_outreach_at <= '2026-07-30 23:59:59'
    ORDER BY l.last_outreach_at
""", (kajal_ids,))
targets = cur.fetchall()
print(f"\nTarget: {len(targets)} leads (last_outreach <= 2026-07-30)")
print("Stage distribution:", dict(Counter(l['followup_stage'] for l in targets)))
print("Email status:", dict(Counter(l['email_status'] for l in targets)))

# Date range check
if targets:
    print(f"Date range: {targets[0]['last_outreach_at']} → {targets[-1]['last_outreach_at']}")

# 3. Apply: close the sequence (keep leads, keep stage)
cur.execute("""
    UPDATE leads_raw
    SET followup_status = 'COMPLETED',
        updated_at = NOW()
    WHERE user_id = ANY(%s)
      AND followup_status = 'ACTIVE'
      AND last_outreach_at IS NOT NULL
      AND last_outreach_at <= '2026-07-30 23:59:59'
""", (kajal_ids,))
updated = cur.rowcount
conn.commit()
print(f"\nUpdated to COMPLETED: {updated}")

# 4. Verify
cur.execute("""
    SELECT followup_status, COUNT(*) n FROM leads_raw
    WHERE user_id = ANY(%s) GROUP BY 1 ORDER BY 2 DESC
""", (kajal_ids,))
print("\nKajal followup_status after:")
for r in cur.fetchall():
    print(f"  {r['followup_status']}: {r['n']}")

cur.execute("""
    SELECT COUNT(*) n FROM leads_raw
    WHERE user_id = ANY(%s) AND followup_status = 'ACTIVE'
      AND last_outreach_at IS NOT NULL AND last_outreach_at <= '2026-07-30 23:59:59'
""", (kajal_ids,))
print(f"\nStill ACTIVE <= 30 Jul (should be 0): {cur.fetchone()['n']}")

conn.close()
print("DONE")
