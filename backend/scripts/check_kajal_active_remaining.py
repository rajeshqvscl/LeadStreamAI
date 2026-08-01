"""Confirm: which leads in Kajal's account (user_id=3) remain ACTIVE after the suppression,
and overall account status breakdown."""
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

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found")
    sys.exit(1)
db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

EMAILS = [
    "moreshwar.panchal@niifindia.in", "pranav@3one4capital.com", "padmaja@iangroup.vc",
    "yournest@yournest.in", "sasha@elev8vp.com", "vidit@anayventures.com",
    "aditya.arora@faad.in", "jehangir@sekhsaria.com", "jordan@motier.vc",
    "vishal.katariya@ankurcapital.com", "sharad.yadav@chimeravc.com", "anurag@bvp.com",
    "deals@dexter.ventures", "nihal.shetty@zerodha.com", "samir@atheravp.com",
    "robin@cornucopiacapital.com", "deepak@catamaran.in", "ATrehan@act.is",
    "mahesh@amicuscapital.in", "rahul@stellarisvp.com", "ea@ankurcapital.com",
    "animesh@udyatventures.com",
]
DOMAINS = sorted({e.strip().lower().split('@')[-1] for e in EMAILS if '@' in e})
ph = ','.join(['%s'] * len(EMAILS))
dph = ','.join(['%s'] * len(DOMAINS))
email_lower = [e.lower() for e in EMAILS]

# Suppressed set = leads under Kajal matching emails/domains
cur.execute(f"""
    SELECT id FROM leads_raw
    WHERE user_id = 3
      AND (LOWER(email) IN ({ph}) OR LOWER(domain) IN ({dph}) OR LOWER(SPLIT_PART(email, '@', 2)) IN ({dph}))
""", email_lower + DOMAINS + DOMAINS)
suppressed_ids = {r['id'] for r in cur.fetchall()}

print("=" * 110)
print("KAJAL ACCOUNT (user_id=3) - status after suppression")
print("=" * 110)

# 1. Overall account breakdown
cur.execute("""
    SELECT COUNT(*) as total FROM leads_raw WHERE user_id = 3
""")
total_leads = cur.fetchone()['total']
print(f"\nTotal leads in Kajal account: {total_leads}")
print(f"Suppressed (your 22 emails + domain employees): {len(suppressed_ids)}")
print(f"Remaining (NOT suppressed): {total_leads - len(suppressed_ids)}")

# 2. Status breakdown of remaining (not-suppressed) leads
cur.execute("""
    SELECT followup_status, email_status, COUNT(*) as cnt
    FROM leads_raw
    WHERE user_id = 3
    GROUP BY followup_status, email_status
    ORDER BY followup_status, email_status
""")
print("\n[STATUS BREAKDOWN - ALL Kajal leads]:")
for r in cur.fetchall():
    print(f"  followup_status={r['followup_status'] or 'NONE':<18} | email_status={r['email_status'] or 'NONE':<18} | {r['cnt']}")

# 3. ACTIVE leads remaining after suppression - mirroring the REAL follow-up engine filter
# (process_outreach_sequences): status ACTIVE, stage < 3, email_status in SENT/OPENED/CLICKED/REPLIED,
# reply_intent not in blocking list, not unsubscribed, not in unsubscribe_list
cur.execute("""
    SELECT id, first_name, last_name, email, company_name, followup_status, followup_stage,
           email_status, is_responded, reply_intent, last_outreach_at,
           first_outreach_subject, last_outreach_subject, source, sector, lead_type
    FROM leads_raw
    WHERE user_id = 3
      AND followup_status = 'ACTIVE'
      AND followup_stage < 3
      AND email_status IN ('SENT', 'OPENED', 'CLICKED', 'REPLIED')
      AND COALESCE(reply_intent, '') NOT IN ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED', 'NEEDS_MORE_INFO')
      AND COALESCE(is_unsubscribed, FALSE) = FALSE
      AND COALESCE(email_opt_in, TRUE) = TRUE
      AND email NOT IN (SELECT email FROM unsubscribe_list)
    ORDER BY last_outreach_at DESC NULLS LAST
""")
active = cur.fetchall()
print(f"\n[STILL ACTIVE & ELIGIBLE FOR FOLLOWUPS - engine-accurate] (not suppressed): {len(active)}")
for r in active[:40]:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    subj = (r['first_outreach_subject'] or r['last_outreach_subject'] or 'N/A')[:70]
    print(f"  ID {r['id']:>6} | {name:<24} | {(r['email'] or ''):<38} | {r['followup_status']} | stage={r['followup_stage']} | replied={bool(r['is_responded'])}")
    print(f"           subject: {subj}")

# 4. ClimateTech campaign leads specifically (not suppressed)
cur.execute("""
    SELECT id, first_name, last_name, email, followup_status, email_status, is_responded, reply_intent
    FROM leads_raw
    WHERE user_id = 3
      AND (COALESCE(first_outreach_subject, '') ILIKE '%ClimateTech%'
           OR COALESCE(first_outreach_subject, '') ILIKE '%Food Waste%'
           OR COALESCE(last_outreach_subject, '') ILIKE '%ClimateTech%'
           OR COALESCE(last_outreach_subject, '') ILIKE '%Food Waste%')
    ORDER BY id
""")
ct = cur.fetchall()
suppressed_ct = [r for r in ct if r['id'] in suppressed_ids]
not_suppressed_ct = [r for r in ct if r['id'] not in suppressed_ids]
print(f"\n[ClimateTech CAMPAIGN leads in Kajal account]: total={len(ct)} | suppressed={len(suppressed_ct)} | still active in campaign={len(not_suppressed_ct)}")
for r in not_suppressed_ct[:40]:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"  ID {r['id']:>6} | {name:<24} | {(r['email'] or ''):<40} | {r['followup_status']} | {r['email_status']} | replied={bool(r['is_responded'])} | {r['reply_intent']}")

cur.close()
conn.close()
print("\nDONE")
