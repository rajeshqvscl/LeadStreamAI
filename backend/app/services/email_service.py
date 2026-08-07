import os
import re
import ssl
import logging
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from the .env file in the current directory
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
logger.info(f"Module initialized with env_path: {env_path}")


def _get_signature_attachments(user_id: Optional[int]) -> list:
    """Fetch the current user's default signature attachment_file list and
    return file dicts ready for MIME inclusion."""
    if not user_id:
        return []
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        # Get the default signature's attachment_file
        cur.execute(
            "SELECT attachment_file FROM user_signatures WHERE user_id = %s ORDER BY is_default DESC, created_at ASC LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return []
        # row is a tuple because of regular cursor
        raw = row[0] if isinstance(row, (tuple, list)) else (row.get('attachment_file') if hasattr(row, 'get') else None)
        if not raw:
            return []
        filenames = [f.strip() for f in raw.split(',') if f.strip()]
        if not filenames:
            return []
        IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico'}
        asset_dir = Path(__file__).resolve().parent.parent.parent / "assets"
        result = []
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in IMAGE_EXTS:
                logger.info(f"Skipping image from signature attachments (inline in body): {fn}")
                continue
            path = asset_dir / fn
            if path.exists():
                import base64
                with open(path, "rb") as f:
                    content_bytes = f.read()
                result.append({
                    "content": base64.b64encode(content_bytes).decode('utf-8'),
                    "filename": fn
                })
                logger.info(f"Loaded signature attachment: {fn}")
            else:
                logger.warning(f"Signature attachment NOT FOUND: {fn} at {path}")
        return result
    except Exception as e:
        logger.error(f"Error fetching signature attachments for user {user_id}: {e}")
        return []

# Per-account email font preference (applies to draft/followup emails).
# The font is applied as the final wrapper in send_email(), so it wins over
# markdown-rendered content that has no inline font-family of its own.
# NOTE: Kajal/Yashika/Palak use plain `sans-serif` (generic sans family).
SANS_SERIF_FONT = "sans-serif"
USER_EMAIL_FONTS = {
    2: "Arial, sans-serif",  # Ayush
    3: SANS_SERIF_FONT,  # Kajal
    4: SANS_SERIF_FONT,  # Yashika
    5: SANS_SERIF_FONT,  # Palak
}
# Default for everyone else (admin/test/vismaya/...) — sans-serif.
# Ayush (2) keeps his own explicit mapping above and is never affected.
DEFAULT_EMAIL_FONT = SANS_SERIF_FONT

# Per-account email font size (applies to the final send_email() wrapper).
# Default for everyone is 15px. Ayush (2) is explicitly kept at 18px.
USER_EMAIL_FONT_SIZES = {
    2: "18px",  # Ayush — keeps the larger size
    3: "14px",  # Kajal — requested smaller size
    4: "15px",  # Yashika — keep at default size
    5: "13px",  # Palak — smaller size
}
DEFAULT_EMAIL_FONT_SIZE = "15px"


def get_user_email_font(user_id) -> str:
    """Resolve the preferred email font for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    return USER_EMAIL_FONTS.get(uid, DEFAULT_EMAIL_FONT)


def get_user_email_font_size(user_id) -> str:
    """Resolve the preferred email font size (px string) for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    return USER_EMAIL_FONT_SIZES.get(uid, DEFAULT_EMAIL_FONT_SIZE)


def strip_old_unsubscribe_links(html_content: str) -> str:
    """Remove legacy inject_signature unsubscribe links from content before the footer.
    Never touches the footer's own link (which is after 'You're receiving this because')."""
    import re as _us
    _footer_text = "You're receiving this because you interacted with LeadStream"
    if _footer_text in html_content:
        _before, _after = html_content.split(_footer_text, 1)
        _before = _us.sub(r'<a\s[^>]*>Click here to unsubscribe</a>', '', _before)
        return _before + _footer_text + _after
    return _us.sub(r'<a\s[^>]*>Click here to unsubscribe</a>', '', html_content)


def build_unsubscribe_footer(lead_id: int) -> str:
    """Build the unsubscribe footer HTML appended to every email body.
    Uses FRONTEND_URL so the link goes to the frontend unsubscribe page.
    Falls back to the backend API if token generation fails.
    """
    if not lead_id:
        return ""
    try:
        from app.models.lead import get_or_create_unsubscribe_token
        _ut = get_or_create_unsubscribe_token(lead_id)
    except Exception as _ut_err:
        logger.error(f"Failed to get unsubscribe token for lead {lead_id}: {_ut_err}")
        _ut = None
    _fu = os.getenv("FRONTEND_URL", "https://leadstreamai.onrender.com").rstrip('/')
    if 'qvscl' in _fu.lower():
        logger.error(f"BLOCKED: FRONTEND_URL contains qvscl.com! Using fallback. Value was: {_fu}")
        _fu = "https://leadstreamai.onrender.com"
    if _ut:
        _uurl = f"{_fu}/unsubscribe?token={_ut}"
    else:
        _bu = os.getenv("BACKEND_URL", "https://lead-backend-g9de.onrender.com").rstrip('/')
        _uurl = f"{_bu}/api/leads/unsubscribe/{lead_id}"
    logger.info(f"UNSUBSCRIBE BODY FOOTER: {_uurl}")
    return f"""
<hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0 10px 0">
<p style="font-size:12px;color:#888;margin:0;line-height:1.5">
You're receiving this because you interacted with LeadStream.
<a href="{_uurl}" style="color:#888;text-decoration:underline">Click here to unsubscribe</a>
</p>"""

def send_email(to_email: str, subject: str, html_content: str, from_email: Optional[str] = None, from_name: Optional[str] = None, attachments: Optional[list] = None, lead_id: Optional[int] = None, is_system_email: bool = False, user_id: Optional[int] = None, cc: Optional[str] = None, thread_id: Optional[str] = None, in_reply_to: Optional[str] = None, template_name: Optional[str] = None) -> tuple:
    """Sends an email via the Gmail API (the only dispatch method; SMTP/Resend fallback removed).

    Returns a 4-tuple: (success: bool, message: str, thread_id: Optional[str], rfc_message_id: Optional[str]).
    """
    load_dotenv(dotenv_path=env_path, override=True)
    
    # Always CC lalit.h@qvscl.com if no CC is explicitly set
    DEFAULT_CC = "lalit.h@qvscl.com"
    if not cc:
        cc = DEFAULT_CC
    # Vismaya ke emails mein sirf rajesh.s@qvscl.com CC karo
    is_vismaya = (
        template_name == 'vismaya_leadstream'
        or (from_name and 'vismaya' in from_name.lower())
        or (from_email and 'vismaya' in from_email.lower())
    )
    if is_vismaya:
        cc = "rajesh.s@qvscl.com"
    
    # Unsubscribe guard: skip sending if lead or email is blacklisted
    if lead_id:
        try:
            from app.database import get_db_connection
            guard_conn = get_db_connection()
            guard_cur = guard_conn.cursor()
            guard_cur.execute(
                "SELECT email_opt_in, is_unsubscribed FROM leads_raw WHERE id = %s",
                (lead_id,)
            )
            guard_row = guard_cur.fetchone()
            if guard_row and (guard_row.get('email_opt_in') is False or guard_row.get('is_unsubscribed')):
                guard_cur.close()
                guard_conn.close()
                logger.info(f"Unsubscribe guard blocked send to lead {lead_id} ({to_email}) — lead is unsubscribed")
                return False, "Lead has unsubscribed", None, None
            guard_cur.close()
            guard_conn.close()
        except Exception as guard_err:
            logger.warning(f"Unsubscribe guard check failed for lead {lead_id}: {guard_err}")
    else:
        # Check global unsubscribe_list when no lead_id is provided
        try:
            from app.database import get_db_connection
            guard_conn = get_db_connection()
            guard_cur = guard_conn.cursor()
            guard_cur.execute("SELECT 1 FROM unsubscribe_list WHERE email = %s", (to_email,))
            if guard_cur.fetchone():
                guard_cur.close()
                guard_conn.close()
                logger.info(f"Unsubscribe guard blocked send to {to_email} — email is in global blacklist")
                return False, "Email is unsubscribed globally", None, None
            guard_cur.close()
            guard_conn.close()
        except Exception:
            pass
    
    import markdown
    # Convert markdown to HTML for a premium look — but ONLY for genuinely
    # plain-text / markdown content. If the body already contains known HTML
    # tags (even when it does NOT start with a tag — e.g. WYSIWYG-edited bodies
    # that begin with raw text like "Dear X,&nbsp;" followed by <div>/<table>
    # markup), pass it through untouched. Otherwise the plain-text fallback
    # below wraps EVERY line — including <table>/<tr>/<th> tags — in <p>
    # elements, which breaks table rendering in Gmail. The known-tag list
    # mirrors markdown_to_html's rich-branch check so prose mentioning things
    # like "<filename>" is never mistaken for HTML.
    if not re.search(r'<(div|table|span|p|h[1-6]|ul|ol|li|br|img|a|strong|em|b|i|u|font)[\s>]', html_content, re.IGNORECASE) and '</' not in html_content:
        # Normalize bullet characters for markdown compatibility
        html_content = html_content.replace('•', '*')
        has_bullet_lines = any(line.strip().startswith('* ') for line in html_content.split('\n'))
        if any(marker in html_content for marker in ['**', '###', '[', '|']) or has_bullet_lines:
            html_content = markdown.markdown(html_content, extensions=['extra', 'nl2br'])
        else:
            # Plain text: wrap each paragraph in <p> tags
            paragraphs = [p.strip() for p in html_content.split('\n\n') if p.strip()]
            html_paragraphs = []
            for p in paragraphs:
                lines = p.split('\n')
                if len(lines) == 1:
                    html_paragraphs.append(f'<p style="margin: 0 0 14px 0; line-height: 1.7;">{lines[0]}</p>')
                else:
                    # Handle line breaks within paragraph
                    for line in lines:
                        line = line.strip()
                        if line == '--':
                            html_paragraphs.append('<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">')
                        elif line:
                            html_paragraphs.append(f'<p style="margin: 0 0 14px 0; line-height: 1.7;">{line}</p>')
            html_content = '\n'.join(html_paragraphs)
    # 1. Prepare default attachments (used by both Gmail and Resend)
    # CRITICAL: Do NOT attach PDFs to follow-up emails! Only attach to the very first email in the sequence.
    # Detect follow-up by thread_id OR by Re: prefix in subject (handles case where thread_id is NULL in DB)
    is_followup = bool(thread_id or in_reply_to or (subject and subject.strip().lower().startswith('re:')))
    
    # Merge any provided attachments with signature attachments
    merged_attachments = list(attachments) if attachments else []
    if not is_followup:
        # Include signature attachments from the user's saved signature
        if user_id and not is_system_email:
            sig_attachments = _get_signature_attachments(int(user_id))
            for sig_att in sig_attachments:
                if not any(a.get('filename') == sig_att['filename'] for a in merged_attachments):
                    merged_attachments.append(sig_att)
                    logger.info(f"Loaded signature attachment: {sig_att['filename']}")
    else:
        logger.info("Outreach is a follow-up email thread. Default attachments skipped.")
    attachments = merged_attachments

    # 3. Strip any old unsubscribe links from legacy signature area (before the footer)
    html_content = strip_old_unsubscribe_links(html_content)

    # 4. Append unsubscribe footer (dedup: skip if already present from draft)
    if "You're receiving this because you interacted with LeadStream" not in html_content:
        html_content += build_unsubscribe_footer(lead_id)

    # 2. Attempt Gmail API Dispatch (Gmail is the only dispatch method now)
    if user_id:
        try:
            from app.services.google_service import get_gmail_service
            import base64
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.application import MIMEApplication
            
            service = None
            try:
                # Local normalization to avoid circular imports
                uid_str = str(user_id) if user_id else "1"
                uid_t = uid_str if uid_str.isdigit() else "1"
                
                service = get_gmail_service(int(uid_t))
                if not service:
                    logger.warning(f"No Gmail service found for user {uid_t}. personalized dispatch skipped.")
            except Exception as e:
                logger.error(f"Error building Gmail service for user {user_id}: {e}")
                pass
            
            if service:
                logger.info(f"Using Google API for personalized dispatch (User ID: {user_id})")
                
                # Use MIMEMultipart('mixed') to handle both HTML and attachments
                msg = MIMEMultipart('mixed')
                
                # Sanitize headers to prevent "folded header contains newline" errors
                clean_to = to_email.replace('\n', ', ').replace('\r', '').strip() if to_email else ""
                clean_subject = subject.replace('\n', ' ').replace('\r', '').strip() if subject else "No Subject"
                
                # Robust sender identity
                raw_from = (f"{from_name} <{from_email}>" if from_name and from_email else (from_email or "system@qvscl.com"))
                clean_from = str(raw_from).replace('\n', ' ').replace('\r', '').strip()

                msg['to'] = clean_to
                msg['from'] = clean_from
                msg['subject'] = clean_subject
                
                # Thread Healing: if in_reply_to is missing but thread_id is present, fetch the last message's Message-ID from Gmail
                if thread_id and not in_reply_to:
                    try:
                        logger.info(f"in_reply_to is missing for thread {thread_id}. Fetching thread metadata to heal thread...")
                        thread_detail = service.users().threads().get(
                            userId='me', 
                            id=thread_id, 
                            format='metadata',
                            metadataHeaders=['Message-ID', 'Message-Id', 'message-id']
                        ).execute()
                        messages = thread_detail.get('messages', [])
                        if messages:
                            last_msg = messages[-1]
                            headers = last_msg.get('payload', {}).get('headers', [])
                            in_reply_to = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)
                            logger.info(f"Successfully healed thread! Extracted Message-ID: {in_reply_to}")
                    except Exception as he:
                        logger.error(f"Failed to dynamically heal thread from Gmail: {he}")

                # Set threading headers for replies (wrapped in < > for RFC compliance)
                if in_reply_to:
                    clean_reply_to = in_reply_to.strip()
                    if not clean_reply_to.startswith('<'):
                        clean_reply_to = f"<{clean_reply_to}>"
                    msg['In-Reply-To'] = clean_reply_to
                    # Accumulate References from the existing thread so non-Gmail clients thread correctly
                    if thread_id:
                        try:
                            thread_detail = service.users().threads().get(
                                userId='me',
                                id=thread_id,
                                format='metadata',
                                metadataHeaders=['References', 'Message-ID']
                            ).execute()
                            thread_msgs = thread_detail.get('messages', [])
                            if thread_msgs:
                                last_headers = thread_msgs[-1].get('payload', {}).get('headers', [])
                                existing_refs = next((h['value'] for h in last_headers if h['name'].lower() == 'references'), '')
                                if existing_refs.strip():
                                    msg['References'] = f"{existing_refs.strip()} {clean_reply_to}"
                                else:
                                    msg['References'] = clean_reply_to
                        except Exception as ref_err:
                            logger.warning(f"Failed to accumulate References from thread {thread_id}: {ref_err}")
                            msg['References'] = clean_reply_to
                    else:
                        msg['References'] = clean_reply_to
                
                if cc:
                    clean_cc = cc.replace('\n', ', ').replace('\r', '').strip()
                    msg['Cc'] = clean_cc
                
                # Add List-Unsubscribe headers for One-Click Unsubscribe
                if lead_id:
                    from app.models.lead import get_or_create_unsubscribe_token
                    try:
                        unsub_token = get_or_create_unsubscribe_token(lead_id)
                    except Exception:
                        unsub_token = None
                    base_url = os.getenv("FRONTEND_URL", "https://leadstreamai.onrender.com").rstrip('/')
                    if 'qvscl' in base_url.lower():
                        logger.error(f"BLOCKED: FRONTEND_URL contains qvscl.com! Using fallback. Value was: {base_url}")
                        base_url = "https://leadstreamai.onrender.com"
                    if unsub_token:
                        unsub_url = f"{base_url.rstrip('/')}/unsubscribe?token={unsub_token}"
                    else:
                        unsub_url = f"{base_url.rstrip('/')}/api/leads/unsubscribe/{lead_id}"
                    logger.info(f"UNSUBSCRIBE URL: List-Unsubscribe URL set to: {unsub_url} (BACKEND_URL={os.getenv('BACKEND_URL', 'NOT SET')})")
                    # Extract clean sender email for mailto unsubscribe
                    import re as _unsub_re
                    _sender_mail = _unsub_re.search(r'[\w.+-]+@[\w.-]+', clean_from)
                    _mailto_addr = _sender_mail.group(0) if _sender_mail else clean_from
                    msg['List-Unsubscribe'] = f"<{unsub_url}>, <mailto:{_mailto_addr}?subject=unsub_{lead_id}>"
                    msg['List-Unsubscribe-Post'] = "List-Unsubscribe=One-Click"

                    import uuid
                    from app.database import get_db_connection
                    tracking_token = str(uuid.uuid4())
                    try:
                        track_conn = get_db_connection()
                        track_cur = track_conn.cursor()
                        track_cur.execute("UPDATE leads_raw SET tracking_token = %s, updated_at = NOW() WHERE id = %s", (tracking_token, lead_id))
                        track_conn.commit()
                        track_cur.close()
                        track_conn.close()
                    except Exception as track_err:
                        logger.warning(f"Failed to save tracking token for lead {lead_id}: {track_err}")
                        tracking_token = None

                    if tracking_token:
                        from urllib.parse import urljoin
                        from app.api.tracking import inject_click_tracking
                        backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
                        # Inject click tracking — replaces link hrefs with tracking redirect URLs
                        html_content = inject_click_tracking(html_content, tracking_token, backend_url.rstrip("/"))
                        # Inject open tracking pixel
                        pixel_url = urljoin(backend_url.rstrip("/") + "/", f"api/track/open/{tracking_token}")
                        pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none" />'
                        html_content = html_content + pixel_html

                # Strip inline font-size from html_content so the wrapper font-size
                # cascades uniformly — this prevents any <span style="font-size:12px">
                # in the saved draft from overriding the wrapper. Tables are EXEMPT:
                # their cell font-sizes (e.g. a 9pt header row) are part of the design
                # and would otherwise all jump to the wrapper size and look wrong.
                import re as _fs_re
                def _strip_fontsize_outside_tables(html: str) -> str:
                    _parts = re.split(r'(<table[^>]*>.*?</table>)', html, flags=re.DOTALL | re.IGNORECASE)
                    for _i, _part in enumerate(_parts):
                        if not _part.lower().startswith('<table'):
                            _parts[_i] = _fs_re.sub(r'font-size\s*:\s*[^;]+;?\s*', '', _part)
                    return ''.join(_parts)
                html_content = _strip_fontsize_outside_tables(html_content)

                # Wrap in clean email template for professional appearance in Gmail
                email_font = get_user_email_font(user_id)
                email_font_size = get_user_email_font_size(user_id)
                html_content = f"""
                <div style="font-family: {email_font}; line-height: 1.6; color: #333333; font-size: {email_font_size};">
                    {html_content}
                </div>
                """

                # Build a plain-text fallback by stripping HTML tags
                import re as _re
                plain_text = _re.sub(r'<br\s*/?>', '\n', html_content)
                plain_text = _re.sub(r'<p[^>]*>', '\n', plain_text)
                plain_text = _re.sub(r'<[^>]+>', '', plain_text)
                plain_text = _re.sub(r'&nbsp;', ' ', plain_text)
                plain_text = _re.sub(r'&amp;', '&', plain_text)
                plain_text = _re.sub(r'&lt;', '<', plain_text)
                plain_text = _re.sub(r'&gt;', '>', plain_text)
                plain_text = _re.sub(r'\n{3,}', '\n\n', plain_text).strip()

                # Attach both text/plain and text/html in an 'alternative' container
                msg_body = MIMEMultipart('alternative')
                msg_body.attach(MIMEText(plain_text, 'plain'))
                msg_body.attach(MIMEText(html_content, 'html'))
                msg.attach(msg_body)
                
                # Attach the files
                if attachments:
                    for attachment in attachments:
                        try:
                            file_data = base64.b64decode(attachment['content'])
                            part = MIMEApplication(file_data, Name=attachment['filename'])
                            part['Content-Disposition'] = f'attachment; filename="{attachment["filename"]}"'
                            msg.attach(part)
                        except Exception as e:
                            logger.error(f"Failed to attach file {attachment.get('filename')}: {e}")
                
                raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
                
                # Build the send body — add threadId if this is a reply
                send_body = {'raw': raw_message}
                if thread_id:
                    send_body['threadId'] = thread_id
                logger.info(f"📧 send_email: thread_id={thread_id!r}, in_reply_to={in_reply_to!r}, lead_id={lead_id}, to={clean_to}, subject={clean_subject}")
                
                # Gmail API send with SSL retry + thread recovery
                try:
                    sent = service.users().messages().send(userId='me', body=send_body).execute()
                except ssl.SSLError as ssl_err:
                    logger.warning(f"SSL error on first attempt for user {user_id}: {ssl_err}. Invalidating cache and retrying...")
                    from app.services.google_service import invalidate_gmail_service_cache
                    invalidate_gmail_service_cache(int(uid_t))
                    service = get_gmail_service(int(uid_t))
                    if service:
                        sent = service.users().messages().send(userId='me', body=send_body).execute()
                    else:
                        raise ssl_err
                except Exception as api_err:
                    err_str = str(api_err)
                    if '404' in err_str and 'not found' in err_str.lower() and thread_id:
                        logger.warning(f"Thread {thread_id} not found in Gmail — retrying without thread_id")
                        send_body.pop('threadId', None)
                        sent = service.users().messages().send(userId='me', body=send_body).execute()
                    else:
                        raise
                sent_thread_id = sent.get('threadId')
                logger.info(f"📧 send_email result: sent_thread_id={sent_thread_id!r}, expected_thread_id={thread_id!r}, match={sent_thread_id == thread_id}")
                
                # Robustly get the RFC Message-ID from the sent message for future In-Reply-To chaining
                import time as py_time
                sent_rfc_message_id = None
                for attempt in range(2):
                    try:
                        sent_msg_detail = service.users().messages().get(
                            userId='me', 
                            id=sent.get('id'), 
                            format='metadata',
                            metadataHeaders=['Message-ID', 'Message-Id', 'message-id']
                        ).execute()
                        headers = sent_msg_detail.get('payload', {}).get('headers', [])
                        sent_rfc_message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)
                        if sent_rfc_message_id:
                            logger.info(f"Successfully retrieved RFC Message-ID on attempt {attempt + 1}: {sent_rfc_message_id}")
                            break
                    except Exception as ex:
                        logger.warning(f"Attempt {attempt + 1} to fetch RFC Message-ID failed: {ex}")
                    py_time.sleep(0.1)
                
                if not sent_rfc_message_id:
                    # Fallback default Message-ID format if fetch failed
                    sent_rfc_message_id = f"<{sent.get('id')}@mail.gmail.com>"
                    logger.warning(f"Could not fetch RFC Message-ID from Gmail API. Using fallback: {sent_rfc_message_id}")

                # ── LEAD OWNERSHIP UPDATE ──
                # After successful send, assign the lead to whoever sent the email.
                # This ensures replies are attributed to the correct user's inbound deals.
                if lead_id and user_id:
                    try:
                        own_conn = get_db_connection()
                        own_cur = own_conn.cursor()
                        own_cur.execute(
                            "UPDATE leads_raw SET user_id = %s, updated_at = NOW() WHERE id = %s AND COALESCE(user_id, 0) != %s",
                            (int(user_id), lead_id, int(user_id))
                        )
                        if own_cur.rowcount > 0:
                            logger.info(f"Lead {lead_id} ownership transferred to user {user_id}")
                        own_conn.commit()
                        own_cur.close()
                        own_conn.close()
                    except Exception as own_err:
                        logger.warning(f"Failed to update lead ownership for {lead_id}: {own_err}")

                logger.info(f"✅ Gmail API dispatch successful to {to_email} (CC: {cc}) — Message ID: {sent.get('id')}")
                return True, "Success", sent_thread_id, sent_rfc_message_id
            else:
                logger.error(f"Gmail service not initialized for User {user_id}. Gmail must be connected to send emails.")
                return False, "Gmail not connected. Please link your Google account in Settings.", None, None
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_content = ""
            if hasattr(e, 'content'):
                error_content = e.content.decode() if hasattr(e.content, 'decode') else str(e.content)
            
            # Invalidate cached service on SSL errors so next call gets a fresh connection
            if isinstance(e, ssl.SSLError):
                try:
                    from app.services.google_service import invalidate_gmail_service_cache
                    invalidate_gmail_service_cache(int(uid_t))
                except Exception:
                    pass
            
            logger.error(f"❌ Gmail API dispatch failed for User {user_id} to {to_email}: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Gmail API error: {str(e)}", None, None

    # No SMTP/Resend fallback — Gmail API is the only dispatch method for outreach
    logger.error(f"Cannot send email to {to_email}: No Gmail connection available for User {user_id}.")
    return False, "Gmail not connected. Please link your Google account in Settings.", None, None

def check_scheduled_emails():
    """
    Checks the database for any emails in 'SCHEDULED' state where
    scheduled_at <= NOW(). Attempts to send them and updates state to SENT.
    """
    try:
        from app.database import get_db_connection
        from app.models.lead import add_activity_log
        import psycopg2.extras
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("""
            SELECT l.id, l.email, l.email_draft, l.cc_email, l.user_id, l.draft_template_used,
                   u.email as sender_email, u.full_name, u.username
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            WHERE l.email_status = 'SCHEDULED'
              AND l.scheduled_at <= NOW()
              AND COALESCE(l.is_responded, FALSE) = FALSE
              AND COALESCE(l.followup_status, '') != 'STOPPED'
              AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
              AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
              AND l.email NOT IN (SELECT email FROM unsubscribe_list)
        """)
        
        due_leads = cur.fetchall()
        
        if not due_leads:
            cur.close()
            conn.close()
            return
            
        logger.info(f"Found {len(due_leads)} scheduled emails due for dispatch.")
        
        for lead in due_leads:
            lead_id = lead['id']
            to_email = lead['email']
            draft_content = lead['email_draft']
            cc_email = lead['cc_email']
            sender_email = lead['sender_email']
            sender_name = lead['full_name'] or lead['username'] or "the team"
            
            if not draft_content or not to_email:
                continue
                
            subject = "Following up"
            body = draft_content
            if "Subject: " in draft_content:
                parts = draft_content.split("\n\n", 1)
                subject = parts[0].replace("Subject: ", "").strip()
                body = parts[1].strip() if len(parts) > 1 else ""
                
            logger.info(f"Dispatching scheduled email to {to_email}")
            
            # Fetch user ID to enable Gmail dispatch
            user_id = lead['user_id']
            from app.api.drafts import markdown_to_html
            success, error_msg, new_thread_id, new_rfc_message_id = send_email(
                to_email=to_email,
                subject=subject,
                html_content=markdown_to_html(body, font_family=get_user_email_font(user_id), font_size=get_user_email_font_size(user_id)),
                from_email=sender_email,
                from_name=sender_name,
                lead_id=lead_id,
                user_id=user_id,
                cc=cc_email,
                template_name=lead.get('draft_template_used')
            )
            
            if success:
                cur.execute("""
                    UPDATE leads_raw 
                    SET email_status = 'SENT', 
                        updated_at = NOW(),
                        last_outreach_at = NOW(),
                        last_outreach_subject = %s,
                        first_outreach_subject = COALESCE(first_outreach_subject, %s),
                        first_outreach_at = COALESCE(first_outreach_at, NOW()),
                        gmail_thread_id = %s,
                        gmail_message_id = %s,
                        followup_status = 'ACTIVE',
                        followup_stage = 0,
                        is_responded = FALSE,
                        replied_at = NULL
                    WHERE id = %s
                """, (subject, subject, new_thread_id, new_rfc_message_id, lead_id))
                conn.commit()
                try:
                    add_activity_log(lead_id, "EMAIL_SENT", f"Scheduled email dispatched automatically", "system")
                except Exception:
                    pass
            else:
                logger.error(f"Failed to send scheduled email {lead_id} to {to_email}")
                
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in check_scheduled_emails: {str(e)}")
def send_admin_report(to_email: str, report_data: dict) -> bool:
    """
    Formulates and sends a high-level MIS (Management Information System) report
    to the administrator, detailing user productivity and system signals.
    """
    user_stats = report_data.get("user_stats", [])
    recent_logs = report_data.get("recent_logs", [])
    target_user = report_data.get("target_user", "All Team Members")
    
    stats_rows = ""
    for user in user_stats:
        stats_rows += f"""
        <tr style="background-color: #0f172a; border-bottom: 1px solid #1e293b;">
            <td style="padding: 14px; font-size: 13px; color: #f8fafc; font-weight: 600;">{user['username']}</td>
            <td style="padding: 14px; font-size: 13px; color: #cbd5e1; text-align: center;">{user['leads_count']}</td>
            <td style="padding: 14px; font-size: 13px; color: #cbd5e1; text-align: center;">{user['sent_count']}</td>
            <td style="padding: 14px; font-size: 13px; color: #8b5cf6; text-align: right; font-weight: bold;">{user['total_count']}</td>
        </tr>
        """

    subject = f"📊 MIS Activity Report: {target_user}"
    
    total_leads = sum(u.get('leads_count', 0) for u in user_stats)
    total_sent = sum(u.get('sent_count', 0) for u in user_stats)
    
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 650px; margin: auto; padding: 40px; border-radius: 16px; background-color: #0f172a; color: #f8fafc;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 1px solid #1e293b; padding-bottom: 20px;">
            <h2 style="color: #f8fafc; margin: 0; font-size: 22px; font-weight: 800;">Management Information System</h2>
            <span style="background-color: #3b82f620; color: #60a5fa; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: bold; border: 1px solid #3b82f640;">{report_data.get('environment', 'Production')}</span>
        </div>
        
        <p style="color: #94a3b8; font-size: 14px; margin-bottom: 35px; line-height: 1.6;">
            The detailed activity audit for <strong style="color: #f8fafc;">{target_user}</strong> has been dynamically generated. Your detailed Microsoft Excel file (.xlsx) containing programmatic pipeline analytics and extensive row-by-row lead data is attached to this email.
        </p>

        <!-- Dynamic Pipeline Breakdown -->
        <h3 style="color: #f8fafc; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px;">Target Pipeline Flow</h3>
        <div style="background-color: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 35px; border: 1px solid #334155;">
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; margin-bottom: 8px;">
                    <span style="color: #cbd5e1;">Leads Acquired</span>
                    <span style="color: #f8fafc;">{total_leads}</span>
                </div>
                <div style="height: 6px; background-color: #0f172a; border-radius: 10px; overflow: hidden;">
                    <div style="height: 100%; width: 100%; background-color: #8b5cf6; border-radius: 10px;"></div>
                </div>
            </div>
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; margin-bottom: 8px;">
                    <span style="color: #cbd5e1;">Successful Outreach</span>
                    <span style="color: #f8fafc;">{total_sent}</span>
                </div>
                <div style="height: 6px; background-color: #0f172a; border-radius: 10px; overflow: hidden;">
                    <div style="height: 100%; width: {(total_sent/total_leads*100) if total_leads > 0 else 0}%; background-color: #10b981; border-radius: 10px;"></div>
                </div>
            </div>
        </div>

        <h3 style="color: #f8fafc; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px;">Primary Statistics</h3>
        <table style="width: 100%; border-collapse: separate; border-spacing: 0; margin-bottom: 40px; border-radius: 8px; overflow: hidden; border: 1px solid #1e293b;">
            <thead style="background-color: #1e293b;">
                <tr>
                    <th style="padding: 14px; text-align: left; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">User</th>
                    <th style="padding: 14px; text-align: center; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">New Leads</th>
                    <th style="padding: 14px; text-align: center; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">Outreach</th>
                    <th style="padding: 14px; text-align: right; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">Actions</th>
                </tr>
            </thead>
            <tbody style="background-color: #0f172a;">
                {stats_rows if stats_rows else '<tr><td colspan="4" style="padding: 24px; text-align: center; color: #64748b; font-size: 13px;">No activity recorded in target period.</td></tr>'}
            </tbody>
        </table>

        <div style="background-color: #3b82f615; padding: 20px; border-radius: 12px; border: 1px solid #3b82f630; text-align: center;">
            <p style="color: #60a5fa; font-size: 13px; font-weight: bold; margin: 0;">
                Please refer to the attached Excel (.xlsx) file for complete graphs, flow charts, and granular data matrices.
            </p>
        </div>

        <p style="text-align: center; margin-top: 40px; color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">
            LeadStreamAI Automated Dispatch
        </p>
    </div>
    """

    # Get admin recipients
    from app.database import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE role = 'ADMIN' LIMIT 1")
    admin = cur.fetchone()
    cur.close()
    conn.close()

    if not admin:
        logger.error("No admin found to receive MIS report.")
        return False

    res = send_email(
        to_email=to_email or admin['email'],
        subject=subject,
        html_content=html_content,
        from_email=admin['email'],
        from_name="LeadStream Intelligence",
        is_system_email=True,
        user_id=1,
        attachments=report_data.get("attachments")
    )
    return res[0] if isinstance(res, tuple) else res
