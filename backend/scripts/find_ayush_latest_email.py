"""
Find Ayush's (user_id=2) most recently sent outreach emails and check
whether each lead is eligible for a follow-up.

Usage:
  python scripts/find_ayush_latest_email.py [--limit N]

Eligibility mirrors the production auto-pilot (process_outreach_sequences):
  - followup_status = 'ACTIVE'
  - followup_stage < max (INVESTOR=3, CLIENT=2)
  - email_status in SENT/OPENED/CLICKED
  - no blocking reply_intent
  - not responded
  - not unsubscribed / opt-in
  - has gmail thread + message id
  - original outreach subject exists
  - not a Defence lead
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path, override=True)
else:
    for alt in ['app/.env', '.env']:
        if os.path.exists(alt):
            load_dotenv(dotenv_path=alt, override=True)
            break

import psycopg2.extras
from app.database import get_db_connection
from app.services.followup_service import (
    get_original_outreach_subject,
    get_template_followup,
    is_generic_followup,
)

AYUSH_UID = 2
LIMIT = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 10

BLOCKING_INTENTS = ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED', 'NEEDS_MORE_INFO')


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Confirm Ayush identity
    cur.execute("SELECT id, username, email, full_name, auto_followup, google_refresh_token IS NOT NULL AS gmail_linked FROM users WHERE id = %s", (AYUSH_UID,))
    ayush = cur.fetchone()
    print(f"USER: {dict(ayush) if ayush else 'NOT FOUND'}")
    if not ayush:
        cur.close(); conn.close(); return

    cur.execute("""
        SELECT l.id, l.first_name, l.last_name, l.email, l.company_name, l.lead_type,
               l.followup_status, l.followup_stage, l.email_status, l.is_responded,
               l.reply_intent, l.is_unsubscribed, l.email_opt_in,
               l.last_outreach_at, l.last_outreach_subject, l.first_outreach_subject,
               l.gmail_thread_id, l.gmail_message_id, l.draft_template_used,
               l.followup_draft, l.email_draft, l.persona, l.sector
        FROM leads_raw l
        WHERE l.user_id = %s
          AND l.email_status IN ('SENT', 'OPENED', 'CLICKED')
          AND l.last_outreach_at IS NOT NULL
        ORDER BY l.last_outreach_at DESC
        LIMIT %s
    """, (AYUSH_UID, LIMIT))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("\nNo sent outreach emails found for Ayush.")
        return

    print(f"\n=== AYUSH'S {len(rows)} MOST RECENT SENT EMAILS ===")
    print(f"{'ID':>6} | {'Lead':<24} | {'Email':<38} | {'Sent at':<20} | stg | status")
    for r in rows:
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or '?'
        sent = r['last_outreach_at'].strftime('%Y-%m-%d %H:%M') if r['last_outreach_at'] else '-'
        print(f"{r['id']:>6} | {name:<24} | {(r['email'] or ''):<38} | {sent:<20} | {r['followup_stage'] or 0:<3} | {r['followup_status'] or '-'}")

    print("\n=== ELIGIBILITY CHECK (top leads only) ===")
    for r in rows[:5]:
        r = dict(r)
        lead_id = r['id']
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or '?'
        stage = r['followup_stage'] or 0
        next_stage = stage + 1
        max_stage = 2 if str(r.get('lead_type') or '').upper() == 'CLIENT' else 3

        orig_subj = get_original_outreach_subject(r)
        thread = r.get('gmail_thread_id')
        msg = r.get('gmail_message_id')

        body = r.get('followup_draft')
        if is_generic_followup(body):
            body = get_template_followup(r, next_stage)

        is_defence = any(kw in ((orig_subj or '') + ' ' + (body or '') + ' ' + (r.get('email_draft') or '') + ' ' + (r.get('persona') or '') + ' ' + (r.get('sector') or '')).lower() for kw in ('defence', 'deeptech', 'idex'))

        problems = []
        if (r['followup_status'] or '') != 'ACTIVE':
            problems.append(f"followup_status={r['followup_status'] or 'NONE'}")
        if stage >= max_stage:
            problems.append(f"stage {stage} >= max {max_stage}")
        if (r['reply_intent'] or '') in BLOCKING_INTENTS:
            problems.append(f"reply_intent={r['reply_intent']}")
        if r['is_responded']:
            problems.append("is_responded=TRUE")
        if r['is_unsubscribed']:
            problems.append("unsubscribed")
        if r['email_opt_in'] is False:
            problems.append("opt_out")
        if not thread or not msg:
            problems.append("no gmail thread")
        if not orig_subj:
            problems.append("no original subject")
        if is_defence:
            problems.append("DEFENCE lead")

        status = "✅ ELIGIBLE" if not problems else "⛔ BLOCKED: " + "; ".join(problems)
        print(f"\n  Lead {lead_id} | {name} <{r['email']}> | {r['company_name'] or ''}")
        print(f"    stage={stage}->{next_stage} | sent_at={r['last_outreach_at']} | subject='{orig_subj or '(none)'}'")
        print(f"    next followup body (template): {body[:160]!r}...")
        print(f"    {status}")


if __name__ == '__main__':
    main()
