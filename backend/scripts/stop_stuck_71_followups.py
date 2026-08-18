"""
Stop followups + mark unsubscribed for the exact 71 leads from the 12-Aug Kajal
outreach that missed their 14-Aug followup (the user-provided list).

Applied when --apply is passed:
  - leads_raw.followup_status = 'STOPPED'
  - leads_raw.is_unsubscribed = TRUE
  - leads_raw.email_opt_in    = FALSE
  - unsubscribe_list          = insert all matched emails (blocks future sends/ingestion)
  - activity_log              = audit entries per lead

Usage:
  python scripts/stop_stuck_71_followups.py            # read-only status report
  python scripts/stop_stuck_71_followups.py --apply    # apply suppression
"""
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

APPLY = '--apply' in sys.argv

# ---------------------------------------------------------------------------
# The exact 71 emails (user-provided list). Multi-email rows split on ' / '.
# ---------------------------------------------------------------------------
RAW_EMAILS = [
    "puneet.bhatia@tpg.com",
    "avr.venkatesa@blackstone.com",
    "ajay.manuja@blackstone.com",
    "rsinha@thl.com",
    "akhil.gupta@blackstone.com",
    "sameer.nayar@blackstone.com",
    "info@xandergroup.com",
    "sy@xandergroup.com",
    "rajat.goyal@sbicapventures.com",
    "kapil.singhal@kkr.com",
    "sanjay.omprakash-nayar@kkr.com",
    "Ajay.Candade@kkr.com / ajay@fractalgp.com",
    "ayshwarya.vikram@kkr.com",
    "bhuvan.srinivasan@kkr.com",
    "kv.kamath@kkr.com",
    "kapil@truenorth.co.in / kapil.singhal@kkr.com",
    "karan.swani@kkr.com",
    "paroksh.gupta@awcapitalltd.com / paroksh.gupta@kkr.com",
    "info@apegroup.com",
    "nilesh.jain@iifl.com",
    "rohit.mantri@motilaloswal.com",
    "vishalt@motilaloswal.com",
    "kanad.chaudhari@motilaloswal.com",
    "ir@miraeassetmf.com",
    "info@miraeassetmf.com",
    "dave.ashish@miraeasset.com",
    "matta.gaurav@miraeasset.com",
    "pareek.shikha@miraeasset.com",
    "arka.rohit@miraeassetmf.co.in",
    "ghosh.plaban@miraeassetmf.co.in",
    "hong.jiyeong@miraeassetmf.co.in",
    "mhatre.sameer@miraeassetmf.co.in",
    "satiya.namant@miraeassetmf.co.in",
    "talukdar.ruptirtha@miraeassetmf.co.in",
    "jha.vinod@miraeassetmf.co.in",
    "mohanty.swarup@miraeasset.com",
    "mohanty.swarup@miraeassetmf.co.in",
    "ir@embassyofficeparks.com",
    "info@embassyofficeparks.com",
    "abhishek@nexusvp.com",
    "kc.ganesh@pratithi.com",
    "sheeba@pratithi.com",
    "raashi@capital-a.in",
    "dipesh_shah77@yahoo.com",
    "prabhakardelhi@yahoo.com",
    "ragkumar88@gmail.com",
    "rajmohan.krishnan@gmail.com",
    "agarwala.alok@gmail.com",
    "searchnelson@gmail.com",
    "klassykp@gmail.com",
    "vinki@loombainvest.com",
    "loomba@loombainvest.com",
    "mohitchawla276@gmail.com",
    "dini@avpn.asia",
    "ramkumar.venkatramani@avpn.asia",
    "vaishali.anandkumar@avpn.asia",
    "victoryharsh@gmail.com",
    "harsh@magmaventures.com",
    "ankur@magmaventures.com",
    "loyalka.v@gmail.com",
    "rc_email@hotmail.com",
    "varun@varunbeverages.com",
    "somnath.ganguly@varunzambia.com",
    "sujay.kotak@varunzambia.com",
    "arun.devanathan@rpsg.in",
    "sagtan@gmail.com",
    "kjain@spginfra.com",
    "juhiagarwal@scanholdings.com",
    "scanholdings@gmail.com",
    "saatvik@somanigroup.com",
    "chairman@everest.tech",
]

# Normalize: lowercase, split multi-email rows
target_emails = set()
for raw in RAW_EMAILS:
    for part in raw.split(" / "):
        part = part.strip().lower()
        if part:
            target_emails.add(part)
print(f"Target emails (unique, normalized): {len(target_emails)}")

# ---------------------------------------------------------------------------
# 1) Leads Kajal emailed on 12 Aug 2026 (the cohort these 71 belong to)
# ---------------------------------------------------------------------------
cur.execute("""
    SELECT DISTINCT al.lead_id
    FROM activity_log al
    WHERE al.action = 'EMAIL_SENT' AND al.performed_by = 'Kajal Narang'
      AND (al.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date = '2026-08-12'
""")
emailed = {r['lead_id'] for r in cur.fetchall()}
ids = list(emailed)
ph = ','.join(['%s'] * len(ids))
print(f"Leads emailed by Kajal on 12 Aug: {len(emailed)}")

# ---------------------------------------------------------------------------
# 2) Match cohort leads whose email (handling \r\n multi-email rows) is in target
# ---------------------------------------------------------------------------
cur.execute(f"""
    SELECT id, first_name, last_name, email, followup_status, followup_stage,
           email_status, is_unsubscribed, email_opt_in
    FROM leads_raw WHERE id IN ({ph})
""", ids)
matched = []
for r in cur.fetchall():
    db_emails = [e.strip().lower() for e in (r['email'] or '').replace('\r\n', '\n').split('\n') if e.strip()]
    if any(e in target_emails for e in db_emails):
        matched.append(r)

matched.sort(key=lambda r: r['id'])
print(f"Matched leads (12-Aug cohort ∩ target emails): {len(matched)}")

for r in matched:
    name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
    print(f"  ID {r['id']:>6} | {name:<28} | {r['email']:<50} | fup={r['followup_status']} stage={r['followup_stage']} es={r['email_status']}")

# Sanity: are there target emails with NO matching lead in the cohort?
matched_db_emails = set()
for r in matched:
    matched_db_emails.update(e.strip().lower() for e in (r['email'] or '').replace('\r\n', '\n').split('\n') if e.strip())
unmatched_targets = target_emails - matched_db_emails
if unmatched_targets:
    print(f"\nWARNING: {len(unmatched_targets)} target emails not found in 12-Aug cohort:")
    for e in sorted(unmatched_targets):
        print(f"    {e}")

if not APPLY:
    print("\n[CHECK COMPLETE - read-only. Run with --apply to stop followups + mark unsubscribed.]")
    cur.close()
    conn.close()
    sys.exit(0)

if not matched:
    print("\nNo leads to suppress. Nothing done.")
    cur.close()
    conn.close()
    sys.exit(0)

ids = [r['id'] for r in matched]

# Stop followups + mark unsubscribed
cur.execute("""
    UPDATE leads_raw
    SET followup_status = 'STOPPED',
        is_unsubscribed = TRUE,
        email_opt_in = FALSE,
        updated_at = NOW()
    WHERE id = ANY(%s::int[])
""", (ids,))
print(f"\n-> STOPPED followups + marked unsubscribed for {cur.rowcount} leads.")

# Add emails to global unsubscribe_list
emails = sorted(matched_db_emails)
inserted = 0
for em in emails:
    try:
        cur.execute("""
            INSERT INTO unsubscribe_list (email, reason, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (em, "Stuck 12-Aug lead - followups stopped (Kajal Narang)", "manual_suppression"))
        inserted += cur.rowcount
    except Exception as e:
        print(f"  ! failed to insert {em}: {e}")
print(f"-> Added {inserted} unique emails to unsubscribe_list (total tracked: {len(emails)}).")

# COMMIT core suppression first so cosmetic audit failures never roll it back
conn.commit()

# Audit log (separate transaction - failures here don't undo suppression)
try:
    for lid in ids:
        cur.execute("""
            INSERT INTO activity_log (lead_id, action, details, performed_by, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (lid, "FOLLOWUP_STOPPED", "Manual suppression - stuck 12-Aug lead, followups stopped (Kajal Narang)", "admin", 3))
    conn.commit()
except Exception as audit_err:
    conn.rollback()
    print(f"  ! Audit log insert failed (suppression already committed): {audit_err}")

print("\n[SUPPRESSION APPLIED]")
cur.close()
conn.close()
