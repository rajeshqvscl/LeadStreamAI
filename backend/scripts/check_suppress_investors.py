"""
Check follow-up / reply status for a list of investor emails AND every lead
sharing the same email domain, then (optionally) suppress follow-ups for all of them.

Usage:
  python scripts/check_suppress_investors.py            # read-only status report
  python scripts/check_suppress_investors.py --apply    # also apply suppression

Suppression applied when --apply is passed:
  - leads_raw.followup_status  = 'STOPPED'
  - leads_raw.is_unsubscribed  = TRUE
  - leads_raw.email_opt_in     = FALSE
  - unsubscribe_list           = insert all unique matching emails (exact + domain-derived)
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
    "moreshwar.panchal@niifindia.in",
    "pranav@3one4capital.com",
    "padmaja@iangroup.vc",
    "yournest@yournest.in",
    "sasha@elev8vp.com",
    "vidit@anayventures.com",
    "aditya.arora@faad.in",
    "jehangir@sekhsaria.com",
    "jordan@motier.vc",
    "vishal.katariya@ankurcapital.com",
    "sharad.yadav@chimeravc.com",
    "anurag@bvp.com",
    "deals@dexter.ventures",
    "nihal.shetty@zerodha.com",
    "samir@atheravp.com",
    "robin@cornucopiacapital.com",
    "deepak@catamaran.in",
    "ATrehan@act.is",
    "mahesh@amicuscapital.in",
    "rahul@stellarisvp.com",
    "ea@ankurcapital.com",
    "animesh@udyatventures.com",
]

DOMAINS = sorted({e.strip().lower().split('@')[-1] for e in EMAILS if '@' in e})

print("=" * 120)
print("CAMPAIGN: Series A+ | ClimateTech Platform Reducing Food Waste & Food Supply Chain Platform")
print(f"SCOPE: {SCOPE_USER_NAME} (user_id={SCOPE_USER_ID}) ONLY")
print(f"MODE: {'APPLY SUPPRESSION' if APPLY else 'READ-ONLY CHECK'}")
print(f"Exact emails: {len(EMAILS)}  |  Domains to block: {len(DOMAINS)}")
print("=" * 120)

# -- STEP 1: Find leads by exact email OR by domain --------------------------
placeholders = ','.join(['%s'] * len(EMAILS))
email_lower = [e.lower() for e in EMAILS]
domain_placeholders = ','.join(['%s'] * len(DOMAINS))

cur.execute(f"""
    SELECT id, first_name, last_name, email, company_name, user_id, user_name,
           followup_status, followup_stage, email_status, is_responded, reply_intent,
           last_outreach_at, first_outreach_subject, last_outreach_subject,
           draft_template_used, is_unsubscribed, email_opt_in, source, lead_type, sector
    FROM leads_raw
    WHERE user_id = %s
      AND (LOWER(email) IN ({placeholders})
       OR LOWER(domain) IN ({domain_placeholders})
       OR LOWER(SPLIT_PART(email, '@', 2)) IN ({domain_placeholders}))
    ORDER BY LOWER(email)
""", [SCOPE_USER_ID] + email_lower + DOMAINS + DOMAINS)

rows = cur.fetchall()
print(f"\n[MATCHED LEADS]: {len(rows)}")
print("-" * 120)
print(f"{'ID':>6} | {'Name':<22} | {'Email':<38} | {'Company':<28} | {'F/Status':<10} | {'Stage':<5} | {'E-Status':<10} | {'Replied':<7} | {'Intent':<18} | {'Unsub':<5}")
print("-" * 120)
for r in rows:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"{r['id']:>6} | {name:<22} | {(r['email'] or ''):<38} | {(r['company_name'] or '')[:28]:<28} | {(r['followup_status'] or '')[:10]:<10} | {r['followup_stage'] or 0:<5} | {(r['email_status'] or '')[:10]:<10} | {str(bool(r['is_responded'])):<7} | {(r['reply_intent'] or '')[:18]:<18} | {str(bool(r['is_unsubscribed'])):<5}")

print("\n[DETAIL] (matched leads):")
for r in rows:
    print(f"\n  ID {r['id']} | {r['first_name'] or ''} {r['last_name'] or ''} | {r['email']} | user_id={r['user_id']} ({r['user_name'] or '?'})")
    print(f"     followup_status={r['followup_status']} | stage={r['followup_stage']} | email_status={r['email_status']} | replied={r['is_responded']} | intent={r['reply_intent']}")
    print(f"     last_outreach_at={r['last_outreach_at']}")
    print(f"     subject: {r['first_outreach_subject'] or r['last_outreach_subject'] or 'N/A'}")
    print(f"     template: {r['draft_template_used'] or 'N/A'} | source={r['source']} | lead_type={r['lead_type']} | sector={r['sector']}")

# -- STEP 2: Show reply / followup activity for matched leads ------------------
print("\n[FOLLOWUP / REPLY ACTIVITY] (activity_log):")
cur.execute(f"""
    SELECT al.lead_id, al.action, al.details, al.performed_by, al.created_at
    FROM activity_log al
    WHERE al.lead_id IN (
        SELECT id FROM leads_raw
        WHERE user_id = %s
          AND (LOWER(email) IN ({placeholders})
           OR LOWER(domain) IN ({domain_placeholders})
           OR LOWER(SPLIT_PART(email, '@', 2)) IN ({domain_placeholders}))
    )
    ORDER BY al.created_at DESC
""", [SCOPE_USER_ID] + email_lower + DOMAINS + DOMAINS)
acts = cur.fetchall()
if not acts:
    print("  (no activity log entries)")
for a in acts[:60]:
    print(f"  lead {a['lead_id']:<6} | {a['created_at']} | {a['action']:<24} | {a['details'] or ''}")

# -- STEP 2.5: Summary stats ------------------------------------------------
print("\n[SUMMARY] Matched leads by followup_status:")
from collections import Counter
fs = Counter((r['followup_status'] or 'NONE') for r in rows)
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

replied = [r for r in rows if r['is_responded']]
if replied:
    print(f"\n[REPLIED] ({len(replied)}):")
    for r in replied:
        name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
        print(f"  ID {r['id']:>6} | {name:<24} | {r['email']:<40} | intent={r['reply_intent']} | {r['followup_status']}")
else:
    print("\n[REPLIED]  (none)")

# -- STEP 3: Domain-only employees (matched by domain but NOT in exact email list) --
exact_ids = set()
cur.execute(f"SELECT id FROM leads_raw WHERE user_id = %s AND LOWER(email) IN ({placeholders})", [SCOPE_USER_ID] + email_lower)
for r in cur.fetchall():
    exact_ids.add(r['id'])
domain_only = [r for r in rows if r['id'] not in exact_ids]
print(f"\n[EXTRA EMPLOYEES AT SAME DOMAINS] (would also be suppressed): {len(domain_only)}")
for r in domain_only:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"  ID {r['id']:>6} | {name:<22} | {r['email']:<42} | {r['company_name'] or ''} | {r['followup_status']}")

# -- STEP 4: Apply suppression --------------------------------------------------
if not APPLY:
    print("\n[CHECK COMPLETE] (read-only). Run with --apply to suppress follow-ups for all matched leads.")
    cur.close()
    conn.close()
    sys.exit(0)

matched_ids = [r['id'] for r in rows]
if not matched_ids:
    print("\n[WARNING] No matched leads to suppress.")
    cur.close()
    conn.close()
    sys.exit(0)

# 4a. Stop follow-ups on matched leads
cur.execute(f"""
    UPDATE leads_raw
    SET followup_status = 'STOPPED',
        is_unsubscribed = TRUE,
        email_opt_in = FALSE,
        updated_at = NOW()
    WHERE id = ANY(%s::int[])
""", (matched_ids,))
print(f"\n[STOPPED] follow-ups for {cur.rowcount} leads (followup_status='STOPPED', unsubscribed).")

# 4b. Add all unique matching emails to global unsubscribe_list (blocks ingestion + sends)
cur.execute(f"""
    SELECT DISTINCT LOWER(email) as email FROM leads_raw
    WHERE user_id = %s
      AND (LOWER(email) IN ({placeholders})
       OR LOWER(domain) IN ({domain_placeholders})
       OR LOWER(SPLIT_PART(email, '@', 2)) IN ({domain_placeholders}))
""", [SCOPE_USER_ID] + email_lower + DOMAINS + DOMAINS)
all_emails = [r['email'] for r in cur.fetchall() if r['email']]

inserted = 0
for em in all_emails:
    try:
        cur.execute("""
            INSERT INTO unsubscribe_list (email, reason, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (em, "Investor do-not-followup (Series A+ ClimateTech campaign)", "manual_suppression"))
        inserted += cur.rowcount
    except Exception as e:
        print(f"  ! failed to insert {em}: {e}")
conn.commit()
print(f"[BLOCKED] Added {inserted} unique emails to unsubscribe_list (total tracked: {len(all_emails)}).")

# 4c. Add activity log entries for audit trail
for lid in matched_ids:
    try:
        cur.execute("""
            INSERT INTO activity_log (lead_id, action, details, performed_by)
            VALUES (%s, %s, %s, %s)
        """, (lid, "FOLLOWUP_STOPPED", "Manual suppression - investor on Series A+ ClimateTech do-not-contact list (email + domain)", "admin"))
    except Exception:
        pass
conn.commit()

print("[SUPPRESSION APPLIED]")
cur.close()
conn.close()
