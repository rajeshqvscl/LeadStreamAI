#!/usr/bin/env python3
"""
Diagnostic: Why only 3 of 18 Stellaris VP company records show drafts in the review queue.

Traces the full pipeline:
  company_registry → insert_lead (leads_raw) → generate_email_internal (email_draft) → get_pending_drafts
"""
import sys, os
from pathlib import Path
from dotenv import load_dotenv

# Load env same as main.py does
env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path, override=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import get_db_connection
import psycopg2.extras, json

conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# ── 1. All Stellaris VP rows in company_registry ──
cur.execute("""
    SELECT cr.id, cr.user_id, cr._is_generated, cr.row_data
    FROM company_registry cr
    WHERE cr.row_data::text ILIKE '%stellaris%'
""")
registry_rows = cur.fetchall()
print(f"\n{'='*70}")
print(f"STEP 1 — company_registry rows matching 'stellaris': {len(registry_rows)}")
print(f"{'='*70}")

emails_in_registry = []
rows_without_email = []
for r in registry_rows:
    data = r['row_data'] if isinstance(r['row_data'], dict) else json.loads(r['row_data'])
    norm = {str(k).lower().replace(" ","").replace("-","").replace("_",""): v for k,v in data.items() if v}
    email = (norm.get("email") or norm.get("emailaddress") or norm.get("workemail") or norm.get("primaryemail"))
    if not email:
        for k, v in data.items():
            val = str(v).strip()
            if "@" in val and "." in val and len(val) > 5 and " " not in val:
                email = val; break
    status = "[OK]" if email else "[NO EMAIL]"
    uid = r['user_id']
    print(f"  registry_id={r['id']:<6} user_id={uid}  _is_generated={r['_is_generated']}  {status}  {email or '(none)'}")
    if email:
        emails_in_registry.append((r['id'], email.strip().lower(), uid))
    else:
        rows_without_email.append(r['id'])

# ── 2. Check leads_raw for those emails ──
print(f"\n{'='*70}")
print(f"STEP 2 — leads_raw lookup for {len(emails_in_registry)} registry emails")
print(f"{'='*70}")

unique_emails = list(set(e for _, e, _ in emails_in_registry))
# Check ALL users' leads for these emails (bulk generate uses user_id)
leads_map = {}  # email → list of lead dicts
if unique_emails:
    cur.execute("""
        SELECT id, email, user_id, email_draft, email_status, email_opt_in, is_unsubscribed,
               first_name, last_name, company_name, created_at
        FROM leads_raw
        WHERE LOWER(email) = ANY(%s)
    """, (unique_emails,))
    leads_map_list = cur.fetchall()
    for lr in leads_map_list:
        em = lr['email'].lower()
        leads_map.setdefault(em, []).append(lr)
    print(f"  Found {len(leads_map_list)} leads_raw rows for {len(leads_map)} unique emails")
    for em in sorted(leads_map.keys()):
        for lr in leads_map[em]:
            has_draft = "[HAS DRAFT]" if lr['email_draft'] else "[NO DRAFT]"
            opt_in = lr['email_opt_in']
            unsub = lr['is_unsubscribed']
            status = lr['email_status'] or 'NULL'
            print(f"    lead_id={lr['id']:<8} email={em:<35} user_id={lr['user_id']}  status={status:<15} opt_in={opt_in}  unsub={unsub}  {has_draft}")
else:
    print("  (no emails to look up)")

# ── 3. Check unsubscribe_list ──
print(f"\n{'='*70}")
print(f"STEP 3 — unsubscribe_list check")
print(f"{'='*70}")
if unique_emails:
    cur.execute("SELECT email FROM unsubscribe_list WHERE LOWER(email) = ANY(%s)", (unique_emails,))
    blocked = [r['email'] for r in cur.fetchall()]
    if blocked:
        print(f"  [WARNING] {len(blocked)} emails BLOCKED by unsubscribe_list:")
        for b in blocked:
            print(f"    - {b}")
    else:
        print("  [OK] No emails in unsubscribe_list")
else:
    print("  (no emails to check)")

# ── 4. Dedup analysis (same email → multiple leads) ──
print(f"\n{'='*70}")
print(f"STEP 4 — Email deduplication analysis (ON CONFLICT (email, user_id))")
print(f"{'='*70}")
for em in sorted(leads_map.keys()):
    if len(leads_map[em]) > 1:
        print(f"  [DUP] Email '{em}' has {len(leads_map[em])} leads -- only MOST RECENT shows in review queue")
        for lr in leads_map[em]:
            print(f"      lead_id={lr['id']}  created={lr['created_at']}  draft={'YES' if lr['email_draft'] else 'NO'}")

# ── 5. Pending-drafts simulation ──
print(f"\n{'='*70}")
print(f"STEP 5 — Simulating get_pending_drafts WHERE clause")
print(f"{'='*70}")
if unique_emails:
    cur.execute("""
        SELECT lr.id, lr.email, lr.email_draft, lr.email_status, lr.email_opt_in, lr.is_unsubscribed,
               lr.first_name, lr.last_name, lr.company_name, lr.created_at, lr.updated_at,
               ROW_NUMBER() OVER (PARTITION BY LOWER(lr.email) ORDER BY COALESCE(lr.updated_at, lr.created_at) DESC) as rn
        FROM leads_raw lr
        WHERE LOWER(lr.email) = ANY(%s)
          AND lr.email_draft IS NOT NULL
          AND (lr.email_opt_in IS NULL OR lr.email_opt_in = TRUE)
          AND (lr.is_unsubscribed IS NULL OR lr.is_unsubscribed = FALSE)
          AND lr.email NOT IN (SELECT email FROM unsubscribe_list)
    """, (unique_emails,))
    visible = cur.fetchall()
    print(f"  Leads that PASS all review-queue filters: {len(visible)}")
    for v in visible:
        print(f"    lead_id={v['id']:<8} email={v['email']:<35} rn={v['rn']}  (rn=1 means it's the one shown)")
    
    # Count how many would be shown (rn=1 only)
    shown = [v for v in visible if v['rn'] == 1]
    print(f"\n  → After dedup: {len(shown)} would appear in review queue")
    
    # Identify missing ones
    all_lead_ids = set()
    for em in leads_map:
        for lr in leads_map[em]:
            all_lead_ids.add(lr['id'])
    shown_ids = set(v['id'] for v in shown)
    missing_ids = all_lead_ids - shown_ids
    
    if missing_ids:
        print(f"\n  ⚠️  {len(missing_ids)} leads WOULD NOT appear. Reasons:")
        for mid in sorted(missing_ids):
            # Find which lead this is
            for em in leads_map:
                for lr in leads_map[em]:
                    if lr['id'] == mid:
                        reasons = []
                        if not lr['email_draft']:
                            reasons.append("NO DRAFT GENERATED")
                        if lr['email_opt_in'] == False:
                            reasons.append("email_opt_in=FALSE")
                        if lr['is_unsubscribed'] == True:
                            reasons.append("is_unsubscribed=TRUE")
                        if lr['email'].lower() in [b.lower() for b in blocked] if unique_emails else False:
                            reasons.append("IN unsubscribe_list")
                        print(f"    lead_id={mid:<8} email={lr['email']:<35}  reasons: {', '.join(reasons) or 'deduped (another lead with same email shown instead)'}")
else:
    print("  (no emails to simulate)")

# ── 6. Summary ──
print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"  Company registry (stellaris):  {len(registry_rows)} rows")
print(f"  Registry rows WITHOUT email:   {len(rows_without_email)}")
print(f"  Unique emails in registry:     {len(unique_emails)}")
leads_with_draft = sum(1 for em in leads_map for lr in leads_map[em] if lr['email_draft'])
print(f"  Leads with email_draft set:    {leads_with_draft}")
print(f"  Leads in unsubscribe_list:     {len(blocked) if unique_emails else 0}")
print(f"  Expected in review queue:      {len(shown) if unique_emails else 0}")

cur.close()
conn.close()
