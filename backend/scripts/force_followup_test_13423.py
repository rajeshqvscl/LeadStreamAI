"""
Forced follow-up test for lead 13423 (amar.k@qvscl.com) / user 9 (test / sravanthi).

Modes:
  python scripts/force_followup_test_13423.py preview   # Step 1 — generate preview, NO send
  python scripts/force_followup_test_13423.py send       # Step 2 — real Gmail send + DB update + activity log

The `send` path mirrors the production auto-pilot flow (process_outreach_sequences):
  followup_draft (or get_template_followup for the lead's draft_template_used) →
  strip old signature → append saved followup signature → markdown_to_html →
  Gmail API send in the existing thread (in_reply_to) → DB stage bump + SENT →
  activity_log AUTO_FOLLOWUP_SENT Stage N.
"""
import sys
import os
import re
# Fix Windows console encoding (emoji/unicode in logs crash cp1252 prints)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load backend/.env BEFORE importing app modules (database.py reads env at import time)
from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path, override=True)
else:
    for alt in ['app/.env', '.env']:
        if os.path.exists(alt):
            load_dotenv(dotenv_path=alt, override=True)
            break

import logging
import psycopg2.extras

from app.database import get_db_connection
from app.services.email_service import send_email, get_user_email_font, get_user_email_font_size
from app.api.drafts import markdown_to_html, get_followup_signature_markdown
from app.services.followup_service import (
    generate_followup_preview,
    get_template_followup,
    get_original_outreach_subject,
    is_generic_followup,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LEAD_ID = 13423
USER_ID = 9

# Allow override via CLI: python script.py send --lead 13992 --user 5
for _i, _arg in enumerate(sys.argv):
    if _arg == '--lead' and _i + 1 < len(sys.argv):
        LEAD_ID = int(sys.argv[_i + 1])
    if _arg == '--user' and _i + 1 < len(sys.argv):
        USER_ID = int(sys.argv[_i + 1])


def step1_preview():
    print("=" * 70)
    print("STEP 1 — PREVIEW (NO SEND)")
    print("=" * 70)
    result = generate_followup_preview(LEAD_ID, USER_ID)
    if "error" in result:
        print(f"PREVIEW ERROR: {result['error']}")
        return False
    print(f"lead_id        : {result['lead_id']}")
    print(f"next_stage     : {result['next_stage']}")
    print(f"subject        : {result['subject']}")
    print("-" * 70)
    print("BODY:")
    print(result['body'])
    print("-" * 70)
    print("FOLLOWUP SIGNATURE (resolved):")
    sig = get_followup_signature_markdown(str(USER_ID))
    print(repr(sig))
    print("NOTE: saved followup signature is appended before HTML conversion.")
    print(f"full_html chars: {len(result['full_html'])}")
    return True


def step2_send():
    print("=" * 70)
    print(f"STEP 2 — FORCED SEND (REAL EMAIL, lead={LEAD_ID} user={USER_ID})")
    print("=" * 70)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute(
        "SELECT l.*, u.email AS sender_email, u.full_name AS sender_name "
        "FROM leads_raw l JOIN users u ON l.user_id = u.id WHERE l.id = %s",
        (LEAD_ID,),
    )
    lead = cur.fetchone()
    if not lead:
        print("LEAD NOT FOUND")
        cur.close()
        conn.close()
        return False

    lead = dict(lead)
    stage = lead['followup_stage'] or 0
    next_stage = stage + 1
    if next_stage > 3:
        print("Sequence already completed (next_stage > 3)")
        cur.close()
        conn.close()
        return False

    existing_thread_id = lead.get('gmail_thread_id')
    existing_msg_id = lead.get('gmail_message_id')
    orig_subject = get_original_outreach_subject(lead)
    subject = f"Re: {orig_subject}"

    print(f"lead email     : {lead['email']}")
    print(f"sender         : {lead['sender_name']} <{lead['sender_email']}>")
    print(f"stage          : {stage} -> next {next_stage}")
    print(f"thread_id      : {existing_thread_id}")
    print(f"msg_id         : {existing_msg_id}")
    print(f"subject        : {subject}")
    print(f"draft_template : {lead.get('draft_template_used')}")
    print(f"lead_type      : {lead.get('lead_type')}")
    print(f"is_responded   : {lead.get('is_responded')}")
    print(f"reply_intent   : {lead.get('reply_intent')}")

    if not existing_thread_id or not existing_msg_id:
        print("!! No gmail_thread_id / gmail_message_id — cannot thread. Aborting send.")
        cur.close()
        conn.close()
        return False

    # 1. Body: saved followup_draft, else template followup for the lead's template
    body = lead.get('followup_draft')
    if is_generic_followup(body):
        body = get_template_followup(lead, next_stage)
    body = body.strip() if body else ""

    # Strip any existing signature from body (production appends its own)
    body = re.split(r'\s*--\s*', body, maxsplit=1)[0].strip()

    if any(kw in body.lower() for kw in ("defence", "deeptech", "idex")):
        print("!! Body contains defence/deeptech keywords — aborting per policy.")
        cur.close()
        conn.close()
        return False

    # 2. Append the user's saved FOLLOWUP signature
    followup_sig = get_followup_signature_markdown(str(USER_ID))
    if followup_sig:
        body = body.rstrip() + f"\n\n{followup_sig}"
    print("-" * 70)
    print("FINAL BODY + SIGNATURE:")
    print(body)
    print("-" * 70)

    body_html = markdown_to_html(body, font_family=get_user_email_font(USER_ID), font_size=get_user_email_font_size(USER_ID))

    # 3. Claim stage BEFORE send (matches production, prevents duplicates)
    cur.execute(
        "UPDATE leads_raw SET followup_stage = %s, followup_status = 'ACTIVE', updated_at = NOW() "
        "WHERE id = %s",
        (next_stage, LEAD_ID),
    )
    conn.commit()
    print(f"Stage claimed: {stage} -> {next_stage}")

    try:
        success, msg, new_thread_id, new_rfc_msg_id = send_email(
            to_email=lead['email'],
            subject=subject,
            html_content=body_html,
            from_email=lead['sender_email'],
            from_name=lead['sender_name'],
            user_id=str(USER_ID),
            thread_id=existing_thread_id,
            in_reply_to=existing_msg_id,
            lead_id=LEAD_ID,
        )
        print(f"send_email -> success={success} msg={msg!r} thread={new_thread_id!r} rfc={new_rfc_msg_id!r}")

        if success:
            cur.execute(
                "UPDATE leads_raw SET last_outreach_at = NOW(), last_outreach_subject = %s, "
                "email_status = 'SENT', "
                "gmail_thread_id = COALESCE(%s, gmail_thread_id), "
                "gmail_message_id = COALESCE(%s, gmail_message_id), "
                "updated_at = NOW() WHERE id = %s",
                (subject, new_thread_id, new_rfc_msg_id, LEAD_ID),
            )
            conn.commit()

            from app.models.lead import add_activity_log
            add_activity_log(LEAD_ID, "AUTO_FOLLOWUP_SENT", f"Stage {next_stage} auto-sent", "system", USER_ID)
            print("Activity log added: AUTO_FOLLOWUP_SENT Stage", next_stage)

            # Post-send verify
            cur.execute(
                "SELECT followup_stage, followup_status, email_status, last_outreach_at, "
                "gmail_thread_id, gmail_message_id, last_outreach_subject "
                "FROM leads_raw WHERE id = %s",
                (LEAD_ID,),
            )
            after = cur.fetchone()
            print("-" * 70)
            print("POST-SEND DB STATE:")
            for k in after.keys():
                print(f"  {k}: {after[k]}")
            cur.execute(
                "SELECT id, lead_id, action, details, created_at FROM activity_log "
                "WHERE lead_id = %s ORDER BY created_at DESC LIMIT 3",
                (LEAD_ID,),
            )
            print("RECENT ACTIVITY LOG:")
            for r in cur.fetchall():
                print(f"  {r['action']}: {r['details']} @ {r['created_at']}")
            return True
        else:
            print(f"!! SEND FAILED: {msg}")
            return False
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'preview'
    if mode == 'send':
        ok = step2_send()
    else:
        ok = step1_preview()
    print(f"\n{'ALL_OK' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)
