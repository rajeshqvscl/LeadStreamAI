"""
Check Yashika (user_id=4) and Palak (user_id=5) accounts:
  1. Which leads have replies (is_responded / email_status REPLIED / reply_intent set)
  2. Was the reply classified and followup_status set correctly per
     reply_workflow_service.determine_followup_status mapping?
  3. Did follow-ups actually STOP after the reply? (batched activity_log comparison)
  4. Real risk group: replied leads with reply_intent IS NULL + followup_status='ACTIVE'
     (engine treats unknown intent as OK to keep sending -> followups continue)

Uses batched queries (3 total per account) to avoid N+1 timeouts.
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

USERS = {4: "Yashika Gupta (yashika.g)", 5: "Palak Jain (palak.j)"}
BLOCKING_INTENT = ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED', 'NEEDS_MORE_INFO')

for uid, uname in USERS.items():
    print("=" * 120)
    print(f"ACCOUNT: {uname} (user_id={uid})")
    print("=" * 120)

    # 1. All leads that have replied
    cur.execute("""
        SELECT id, first_name, last_name, email, company_name, followup_status, followup_stage,
               email_status, is_responded, reply_intent, updated_at, last_outreach_at,
               first_outreach_subject
        FROM leads_raw
        WHERE user_id = %s
          AND (is_responded = TRUE
               OR email_status = 'REPLIED'
               OR reply_intent IS NOT NULL)
        ORDER BY updated_at DESC
    """, (uid,))
    replied = cur.fetchall()
    replied_ids = [r['id'] for r in replied]
    id_set = set(replied_ids)

    print(f"\n[REPLIED LEADS]: {len(replied)}")

    # 2. Status after reply: did followups stop correctly? (no DB round trips)
    stopped_ok = 0
    problems = []
    unclassified = []
    for r in replied:
        intent = r['reply_intent'] or ''
        fs = (r['followup_status'] or '').upper()
        if intent in ('NOT_INTERESTED', 'NEEDS_MORE_INFO'):
            if fs == 'STOPPED':
                stopped_ok += 1
            else:
                problems.append((r, f"decline/more-info intent '{intent}' but followup_status={fs}"))
        elif intent in ('INTERESTED', 'MEETING_REQUESTED'):
            if fs == 'MEETING_REQUIRED':
                stopped_ok += 1
            else:
                problems.append((r, f"positive intent '{intent}' but followup_status={fs}"))
        elif not intent:
            unclassified.append(r)

    print(f"\n[FOLLOW-UP STOP CHECK] (reply intent vs followup_status):")
    print(f"  Follow-ups stopped correctly: {stopped_ok}/{len(replied)}")
    if problems:
        print(f"  PROBLEM LEADS ({len(problems)}):")
        for r, why in problems[:30]:
            name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
            print(f"    ID {r['id']:>6} | {name:<24} | {r['email']:<40} | {why}")
        if len(problems) > 30:
            print(f"    ... and {len(problems) - 30} more")
    else:
        print("  No mapping problems.")

    # 3. Batched: collect all followup sends per lead
    sends_by_lead = {}
    if replied_ids:
        cur.execute("""
            SELECT lead_id, action, details, created_at
            FROM activity_log
            WHERE lead_id = ANY(%s::int[])
              AND action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED', 'FOLLOWUP_SENT')
            ORDER BY created_at ASC
        """, (replied_ids,))
        for row in cur.fetchall():
            sends_by_lead.setdefault(row['lead_id'], []).append(row)

        # Batched: reply signals
        # Signal A: FOLLOWUP_STOPPED with 'Reply received' (same-company / same-email auto-stops)
        cur.execute("""
            SELECT lead_id, MIN(created_at) as t
            FROM activity_log
            WHERE lead_id = ANY(%s::int[]) AND action = 'FOLLOWUP_STOPPED'
              AND details ILIKE 'Reply received%%'
            GROUP BY lead_id
        """, (replied_ids,))
        reply_sig_a = {r['lead_id']: r['t'] for r in cur.fetchall()}
        # Signal B: RESPONDED action (manual mark-as-responded)
        cur.execute("""
            SELECT lead_id, MIN(created_at) as t
            FROM activity_log
            WHERE lead_id = ANY(%s::int[]) AND action = 'RESPONDED'
            GROUP BY lead_id
        """, (replied_ids,))
        reply_sig_b = {r['lead_id']: r['t'] for r in cur.fetchall()}

    print("\n[FOLLOW-UP SENT AFTER REPLY] (should ideally be none):")
    sent_after = []
    no_signal_sends = []  # replied lead has sends but NO reply signal -> cannot prove order -> manual review
    for lid in replied_ids:
        sends = sends_by_lead.get(lid, [])
        if not sends:
            continue
        reply_time = reply_sig_a.get(lid) or reply_sig_b.get(lid)
        if not reply_time:
            no_signal_sends.append((lid, sends))
            continue
        for s in sends:
            if s['created_at'] and s['created_at'] > reply_time:
                sent_after.append((lid, s, reply_time))
                break

    if not sent_after and not no_signal_sends:
        print("  No follow-up was sent after any reply (per available reply signals).")
    else:
        if sent_after:
            print(f"  CONFIRMED follow-ups sent after reply ({len(sent_after)}):")
            for lid, s, rt in sent_after:
                r = next((x for x in replied if x['id'] == lid), None)
                name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip() if r else '?'
                print(f"    ID {lid:>6} | {name:<24} | {(r['email'] if r else ''):<40} | reply@{rt} | {s['action']}@{s['created_at']} | {s['details'] or ''}")
        if no_signal_sends:
            print(f"  NEEDS MANUAL REVIEW - replied lead has follow-up sends but no reply signal found ({len(no_signal_sends)}):")
            for lid, sends in no_signal_sends[:30]:
                r = next((x for x in replied if x['id'] == lid), None)
                name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip() if r else '?'
                latest = sends[-1]
                print(f"    ID {lid:>6} | {name:<24} | {(r['email'] if r else ''):<40} | intent={(r['reply_intent'] if r else '-')} | status={(r['followup_status'] if r else '-')} | latest send: {latest['action']}@{latest['created_at']}")
            if len(no_signal_sends) > 30:
                print(f"    ... and {len(no_signal_sends) - 30} more")

    # 4. REAL RISK GROUP: replied + reply_intent NULL + followup_status ACTIVE
    #    (engine only re-verifies blocking intents before sending -> these keep getting followups)
    risk = [r for r in replied if not (r['reply_intent'] or '') and (r['followup_status'] or '').upper() == 'ACTIVE']
    print(f"\n[REAL RISK - REPLIED BUT UNCLASSIFIED + STILL ACTIVE] (followups may continue): {len(risk)}")
    for r in risk[:40]:
        name = f"{(r['first_name'] or '')} {(r['last_name'] or '')}".strip()
        print(f"  ID {r['id']:>6} | {name:<24} | {r['email']:<40} | stage={r['followup_stage']} | email_status={r['email_status']}")
    if len(risk) > 40:
        print(f"  ... and {len(risk) - 40} more")

    # 5. Also show replied-but-unclassified summary (all, not just ACTIVE)
    print(f"\n[REPLIED BUT reply_intent EMPTY (unclassified)]: {len(unclassified)}")
    print(f"[STILL ACTIVE with blocking reply_intent] (engine skips at send time): {sum(1 for r in replied if (r['followup_status'] or '').upper() == 'ACTIVE' and r['reply_intent'])}")
    print()

cur.close()
conn.close()
print("DONE")
