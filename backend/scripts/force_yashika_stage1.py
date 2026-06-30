import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
import time
import re
from datetime import datetime, timezone, timedelta
import psycopg2.extras

from app.database import get_db_connection
from app.services.email_service import send_email
from app.api.drafts import get_sender_profile, markdown_to_html
from app.services.followup_service import get_template_followup, get_original_outreach_subject, is_generic_followup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

YASHIKA_UID = 4

def force_send_stage1():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT l.*, u.email as sender_email, u.full_name as sender_name
        FROM leads_raw l
        JOIN users u ON l.user_id = u.id
        WHERE l.user_id = %s
        AND l.followup_stage = 0
        AND l.followup_status = 'ACTIVE'
        AND l.email_status IN ('SENT', 'OPENED', 'CLICKED')
        AND COALESCE(l.is_responded, FALSE) = FALSE
        AND COALESCE(l.reply_intent, '') NOT IN ('INTERESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED')
        AND l.last_outreach_at IS NOT NULL
        AND l.last_outreach_at <= NOW() - INTERVAL '2 days'
        ORDER BY l.last_outreach_at ASC
    """, (YASHIKA_UID,))

    leads = cur.fetchall()
    cur.close()
    conn.close()

    logger.info(f"Found {len(leads)} due stage-1 leads for Yashika")

    sent = 0
    skipped = 0
    errors = 0

    for lead in leads:
        lead = dict(lead)
        lead_id = lead['id']
        stage = lead['followup_stage'] or 0
        next_stage = stage + 1

        if stage >= 3:
            logger.info(f"Lead {lead_id}: stage >= 3, skipping")
            continue

        # Get thread info for threading
        existing_thread_id = lead.get('gmail_thread_id')
        existing_msg_id = lead.get('gmail_message_id')

        if not existing_thread_id or not existing_msg_id:
            logger.info(f"Lead {lead_id}: no Gmail thread, skipping")
            skipped += 1
            continue

        # Get original subject
        orig_subject = get_original_outreach_subject(lead)
        if not orig_subject:
            logger.info(f"Lead {lead_id}: no original subject, skipping")
            skipped += 1
            continue
        subject = f"Re: {orig_subject}"

        # Get followup body
        body = lead.get('followup_draft')
        if is_generic_followup(body):
            body = get_template_followup(lead, next_stage)

        body = re.split(r'\s*--\s*', body, maxsplit=1)[0].strip()

        # Skip defence leads
        if any(kw in body.lower() for kw in ("defence", "deeptech", "idex")):
            logger.info(f"Lead {lead_id}: Defence lead, skipping")
            skipped += 1
            continue

        # Build HTML body with signature
        profile = get_sender_profile(str(YASHIKA_UID))
        name = profile.get('full_name') or profile.get('username') or 'Team'
        name = " ".join([p.capitalize() for p in name.split()])
        first_name = name.split()[0] if name else name

        body_html = markdown_to_html(body)
        sig_html = f'<p style="margin-top: 4px;">--<br>Regards,<br>{first_name}</p>'
        full_body = body_html + sig_html

        # Update lead stage immediately
        claim_conn = get_db_connection()
        claim_cur = claim_conn.cursor()
        new_status = 'ACTIVE'
        claim_cur.execute("""
            UPDATE leads_raw
            SET followup_stage = %s, followup_status = %s, updated_at = NOW()
            WHERE id = %s
        """, (next_stage, new_status, lead_id))
        claim_conn.commit()
        claim_cur.close()
        claim_conn.close()

        try:
            success, msg, new_thread_id, new_rfc_msg_id = send_email(
                to_email=lead['email'],
                subject=subject,
                html_content=full_body,
                from_email=lead.get('sender_email') or 'yashika.g@qvscl.com',
                from_name=lead.get('sender_name') or 'Yashika',
                user_id=str(YASHIKA_UID),
                thread_id=existing_thread_id,
                in_reply_to=existing_msg_id,
                lead_id=lead_id
            )

            if success:
                update_conn = get_db_connection()
                update_cur = update_conn.cursor()
                update_cur.execute("""
                    UPDATE leads_raw
                    SET last_outreach_at = NOW(), last_outreach_subject = %s,
                        email_status = 'SENT',
                        gmail_thread_id = COALESCE(%s, gmail_thread_id),
                        gmail_message_id = COALESCE(%s, gmail_message_id),
                        updated_at = NOW()
                    WHERE id = %s
                """, (subject, new_thread_id, new_rfc_msg_id, lead_id))
                update_conn.commit()
                update_cur.close()
                update_conn.close()

                from app.models.lead import add_activity_log
                add_activity_log(lead_id, "AUTO_FOLLOWUP_SENT", f"Stage {next_stage} auto-sent", "system", YASHIKA_UID)

                sent += 1
                if sent % 10 == 0:
                    logger.info(f"Progress: {sent}/{len(leads)} sent")
                time.sleep(1)
            else:
                logger.error(f"Failed to send to {lead['email']}: {msg}")
                errors += 1

        except Exception as e:
            logger.error(f"Error sending to {lead['email']} (ID={lead_id}): {e}")
            errors += 1

    logger.info(f"\n=== DONE ===")
    logger.info(f"Sent: {sent}, Skipped: {skipped}, Errors: {errors}, Total: {len(leads)}")

if __name__ == '__main__':
    force_send_stage1()
