"""
Send follow-up STAGE 1 to Sravanthi ONLY (lead id 17766, user 3 / Kajal).
Single-lead, production-mirroring path. Created to work around broken
followup_service import chain in the repo.

Run: python scripts/send_sravanthi_followup1.py
"""
import sys
import os
import re

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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
from app.services.email_service import (
    send_email, get_user_email_font, get_user_email_font_size,
    get_user_image_width, get_user_image_height,
)
from app.api.drafts import markdown_to_html, get_followup_signature_markdown, clean_first_name
from app.models.lead import add_activity_log

LEAD_ID = 17766
USER_ID = 3


def main():
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
        return
    lead = dict(lead)

    stage = lead['followup_stage'] or 0
    next_stage = stage + 1
    print(f"lead email : {lead['email']}")
    print(f"sender     : {lead['sender_name']} <{lead['sender_email']}>")
    print(f"stage      : {stage} -> next {next_stage}")
    print(f"template   : {lead.get('draft_template_used')}")
    print(f"thread_id  : {lead.get('gmail_thread_id')}")
    print(f"msg_id     : {lead.get('gmail_message_id')}")

    if not lead.get('gmail_thread_id') or not lead.get('gmail_message_id'):
        print("!! No gmail_thread_id / gmail_message_id — cannot thread. Aborting.")
        return

    # 1. Body: followup_1 from the lead's template
    cur.execute(
        "SELECT followup_1 FROM prompts WHERE name = %s AND prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE",
        (lead.get('draft_template_used'),),
    )
    prow = cur.fetchone()
    followup_1 = prow['followup_1'] if prow and prow['followup_1'] else None
    if not followup_1:
        print("!! No followup_1 found for template. Aborting.")
        return

    f_name = clean_first_name(lead)
    body = (followup_1
            .replace("{{First Name}}", f_name)
            .replace("{{first name}}", f_name)
            .replace("{{first_name}}", f_name))

    # 2. Strip any existing signature, then append saved follow-up signature
    body = re.split(r'\s*--\s*', body, maxsplit=1)[0].strip()
    followup_sig = get_followup_signature_markdown(str(USER_ID))
    if followup_sig:
        body = body.rstrip() + f"\n\n{followup_sig}"

    print("-" * 70)
    print("FINAL BODY + SIGNATURE:")
    print(body)
    print("-" * 70)

    # 3. Subject: Re: original outreach subject
    orig_subject = lead.get('first_outreach_subject') or lead.get('last_outreach_subject') or ''
    subject = f"Re: {orig_subject}"
    print(f"subject    : {subject}")

    body_html = markdown_to_html(
        body,
        font_family=get_user_email_font(USER_ID),
        font_size=get_user_email_font_size(USER_ID),
        image_width=get_user_image_width(USER_ID),
        image_height=get_user_image_height(USER_ID),
    )

    # 4. Claim stage BEFORE send
    cur.execute(
        "UPDATE leads_raw SET followup_stage = %s, followup_status = 'ACTIVE', updated_at = NOW() WHERE id = %s",
        (next_stage, LEAD_ID),
    )
    conn.commit()
    print(f"Stage claimed: {stage} -> {next_stage}")

    # 5. Send in the existing thread
    success, msg, new_thread_id, new_rfc_msg_id = send_email(
        to_email=lead['email'],
        subject=subject,
        html_content=body_html,
        from_email=lead['sender_email'],
        from_name=lead['sender_name'],
        user_id=str(USER_ID),
        thread_id=lead.get('gmail_thread_id'),
        in_reply_to=lead.get('gmail_message_id'),
        lead_id=LEAD_ID,
    )
    print(f"send_email -> success={success} msg={msg!r}")

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
        add_activity_log(LEAD_ID, "FOLLOWUP_APPROVED", "Stage 1 follow-up sent to Sravanthi (manual)", "user", USER_ID)
        print("DONE: follow-up 1 sent to Sravanthi only (lead 17766).")
    else:
        print(f"!! SEND FAILED: {msg}")


if __name__ == '__main__':
    main()
