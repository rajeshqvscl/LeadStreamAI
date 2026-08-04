"""
Suppress 5 specific do-not-contact emails under KAJAL's account (user_id=3).

These 5 people must never receive email:
  saurabh@alpha.co.in      (Saurabh Agarwal)
  saket.sah@rpsg.in
  ds@malpaniventures.com
  rahul@stellarisvp.com
  info@act.is

Usage:
  python scripts/suppress_specific_emails_kajal.py            # read-only status report
  python scripts/suppress_specific_emails_kajal.py --apply    # apply suppression

Suppression applied when --apply is passed:
  - leads_raw.followup_status  = 'STOPPED'
  - leads_raw.is_unsubscribed  = TRUE
  - leads_raw.email_opt_in     = FALSE
  - unsubscribe_list           = insert all unique matching emails (blocks ingestion + sends)
  - activity_log               = audit entries per lead
"""
import sys
import os
from dotenv import load_dotenv

# Force UTF-8 output so rupee symbols / unicode don't crash on cp1252 Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env", "../../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
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

# Scope: only Kajal's account (user_id=3) per user request
SCOPE_USER_ID = 3
SCOPE_USER_NAME = 'Kajal Narang (kajal.n)'

EMAILS = [
    "saurabh@alpha.co.in",
    "saket.sah@rpsg.in",
    "ds@malpaniventures.com",
    "rahul@stellarisvp.com",
    "info@act.is",
]

# Exact-email only (no domain-wide blocking for these 5) — do-not-contact is per person.
# Domain-matched leads are listed for transparency but NOT suppressed unless --apply-include-domain is passed.

print("=" * 120)
print(f"MODE: {'APPLY SUPPRESSION' if APPLY else 'READ-ONLY CHECK'}")
print(f"SCOPE: {SCOPE_USER_NAME} (user_id={SCOPE_USER_ID}) ONLY")
print(f"Emails to block (exact): {len(EMAILS)}")
print("=" * 120)

placeholders = ','.join(['%s'] * len(EMAILS))
email_lower = [e.lower() for e in EMAILS]

# -- STEP 1: Find leads by exact email -----------------------------------------
cur.execute(f"""
    SELECT id, first_name, last_name, email, company_name, user_id, user_name,
           followup_status, followup_stage, email_status, is_responded, reply_intent,
           last_outreach_at, first_outreach_subject, last_outreach_subject,
           draft_template_used, is_unsubscribed, email_opt_in, source, lead_type, sector
    FROM leads_raw
    WHERE user_id = %s
      AND LOWER(email) IN ({placeholders})
    ORDER BY LOWER(email)
""", [SCOPE_USER_ID] + email_lower)

rows = cur.fetchall()
print(f"\n[MATCHED LEADS - exact email]: {len(rows)}")
print("-" * 140)
print(f"{'ID':>6} | {'Name':<22} | {'Email':<32} | {'Company':<24} | {'F/Status':<12} | {'Stage':<5} | {'E-Status':<12} | {'Replied':<7} | {'Intent':<18} | {'Unsub':<5}")
print("-" * 140)
for r in rows:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"{r['id']:>6} | {name:<22} | {(r['email'] or ''):<32} | {(r['company_name'] or '')[:24]:<24} | {(r['followup_status'] or '')[:12]:<12} | {r['followup_stage'] or 0:<5} | {(r['email_status'] or '')[:12]:<12} | {str(bool(r['is_responded'])):<7} | {(r['reply_intent'] or '')[:18]:<18} | {str(bool(r['is_unsubscribed'])):<5}")

print("\n[DETAIL] (matched leads):")
for r in rows:
    print(f"\n  ID {r['id']} | {r['first_name'] or ''} {r['last_name'] or ''} | {r['email']} | user_id={r['user_id']} ({r['user_name'] or '?'})")
    print(f"     followup_status={r['followup_status']} | stage={r['followup_stage']} | email_status={r['email_status']} | replied={r['is_responded']} | intent={r['reply_intent']}")
    print(f"     last_outreach_at={r['last_outreach_at']}")
    print(f"     subject: {r['first_outreach_subject'] or r['last_outreach_subject'] or 'N/A'}")
    print(f"     template: {r['draft_template_used'] or 'N/A'} | source={r['source']} | lead_type={r['lead_type']} | sector={r['sector']}")

# -- STEP 1.5: Check emails NOT found as leads (still add to unsubscribe_list later) --
found_emails = {r['email'].lower() for r in rows if r.get('email')}
missing = [e for e in email_lower if e not in found_emails]
if missing:
    print(f"\n[NOT FOUND AS LEADS in Kajal account] (will still be added to global unsubscribe_list):")
    for e in missing:
        print(f"  {e}")

# -- STEP 2: Show followup / send activity for matched leads ------------------
print("\n[ACTIVITY LOG] (matched leads):")
if rows:
    ids = [r['id'] for r in rows]
    cur.execute("""
        SELECT al.lead_id, al.action, al.details, al.performed_by, al.created_at
        FROM activity_log al
        WHERE al.lead_id = ANY(%s::int[])
        ORDER BY al.created_at DESC
    """, (ids,))
    acts = cur.fetchall()
    if not acts:
        print("  (no activity log entries)")
    for a in acts[:60]:
        print(f"  lead {a['lead_id']:<6} | {a['created_at']} | {a['action']:<24} | {a['details'] or ''}")
else:
    print("  (no matched leads)")

# -- STEP 3: Domain-only employees (informational only, NOT suppressed) --------
domains = sorted({e.split('@')[-1] for e in email_lower if '@' in e})
domain_placeholders = ','.join(['%s'] * len(domains))
cur.execute(f"""
    SELECT id, first_name, last_name, email, company_name, followup_status
    FROM leads_raw
    WHERE user_id = %s
      AND LOWER(SPLIT_PART(email, '@', 2)) IN ({domain_placeholders})
      AND LOWER(email) NOT IN ({placeholders})
    ORDER BY LOWER(email)
""", [SCOPE_USER_ID] + domains + email_lower)
domain_only = cur.fetchall()
print(f"\n[OTHER LEADS AT SAME DOMAINS - NOT suppressed] (informational): {len(domain_only)}")
for r in domain_only:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"  ID {r['id']:>6} | {name:<22} | {r['email']:<42} | {r['company_name'] or ''} | {r['followup_status']}")

# -- STEP 4: Summary ----------------------------------------------------------
from collections import Counter
fs = Counter((r['followup_status'] or 'NONE') for r in rows)
print("\n[SUMMARY] Matched leads by followup_status:")
for k, v in fs.most_common():
    print(f"  {k:<22} {v}")

still_active = [r for r in rows if (r['followup_status'] or '').upper() in ('ACTIVE', 'SCHEDULED', 'PENDING_APPROVAL', 'APPROVED')]
if still_active:
    print(f"\n[STILL ACTIVE / SCHEDULED] ({len(still_active)}) - these MUST be stopped:")
    for r in still_active:
        name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
        print(f"  ID {r['id']:>6} | {name:<24} | {r['email']:<40} | {r['followup_status']} | stage={r['followup_stage']} | replied={bool(r['is_responded'])} | intent={r['reply_intent']}")
else:
    print("\n[STILL ACTIVE / SCHEDULED]  (none)")

# -- STEP 5: Apply suppression --------------------------------------------------
if not APPLY:
    print("\n[CHECK COMPLETE] (read-only). Run with --apply to suppress all matched leads.")
    cur.close()
    conn.close()
    sys.exit(0)

matched_ids = [r['id'] for r in rows]
if not matched_ids:
    print("\n[WARNING] No matched leads to suppress. Adding emails to unsubscribe_list anyway.")

# 5a. Stop follow-ups on matched leads
if matched_ids:
    cur.execute(f"""
        UPDATE leads_raw
        SET followup_status = 'STOPPED',
            is_unsubscribed = TRUE,
            email_opt_in = FALSE,
            updated_at = NOW()
        WHERE id = ANY(%s::int[])
    """, (matched_ids,))
    print(f"\n[STOPPED] follow-ups for {cur.rowcount} leads (followup_status='STOPPED', unsubscribed).")

# 5b. Add all target emails to global unsubscribe_list (blocks ingestion + sends)
inserted = 0
for em in email_lower:
    try:
        cur.execute("""
            INSERT INTO unsubscribe_list (email, reason, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (em, "Do-not-contact - user requested suppression (5 specific emails)", "manual_suppression"))
        inserted += cur.rowcount
    except Exception as e:
        print(f"  ! failed to insert {em}: {e}")
conn.commit()
print(f"[BLOCKED] Added {inserted} unique emails to unsubscribe_list.")

# 5c. Add activity log entries for audit trail
if matched_ids:
    for lid in matched_ids:
        try:
            cur.execute("""
                INSERT INTO activity_log (lead_id, action, details, performed_by, user_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (lid, "FOLLOWUP_STOPPED", "Manual suppression - do-not-contact (5 specific emails, Kajal account)", "admin", SCOPE_USER_ID))
        except Exception:
            pass
    conn.commit()

print("[SUPPRESSION APPLIED]")
cur.close()
conn.close()
