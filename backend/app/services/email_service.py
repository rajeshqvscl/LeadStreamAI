import os
import ssl
import logging
import resend
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

# Configure Resend
resend.api_key = os.getenv("RESEND_API_KEY")

def send_smtp_fallback(to_email: str, subject: str, html_content: str, from_email: str, from_name: str, reply_to: Optional[str] = None, cc: Optional[str] = None) -> bool:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    sender_line = f"{from_name} <{from_email}>"
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_line
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if cc:
            msg['Cc'] = cc
            
        if reply_to:
            msg['Reply-To'] = reply_to
        else:
            msg['Reply-To'] = from_email
            
        import re as _re2
        _plain_text = _re2.sub(r'<br\s*/?>', '\n', html_content)
        _plain_text = _re2.sub(r'<p[^>]*>', '\n', _plain_text)
        _plain_text = _re2.sub(r'<[^>]+>', '', _plain_text)
        _plain_text = _re2.sub(r'&nbsp;', ' ', _plain_text)
        _plain_text = _re2.sub(r'&amp;', '&', _plain_text)
        _plain_text = _re2.sub(r'&lt;', '<', _plain_text)
        _plain_text = _re2.sub(r'&gt;', '>', _plain_text)
        _plain_text = _re2.sub(r'\n{3,}', '\n\n', _plain_text).strip()
        alt_body = MIMEMultipart('alternative')
        alt_body.attach(MIMEText(_plain_text, 'plain'))
        alt_body.attach(MIMEText(html_content, 'html'))
        msg.attach(alt_body)

        # Prepare recipient list
        recipients = [to_email]
        if cc:
            # Handle multiple CCs separated by commas
            cc_list = [c.strip() for c in cc.split(',')]
            recipients.extend(cc_list)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, recipients, msg.as_string())
        server.quit()
        logger.info(f"Email sent successfully via SMTP to {to_email} (CC: {cc})")
        return True
    except Exception as e:
        logger.error(f"SMTP Dispatch Error: {str(e)}")
        return False

def format_outreach_html(text: str) -> str:
    """
    Converts markdown-style bold, bullets, and links into clean HTML.
    Specifically targets:
    - **Bold** -> <strong>
    - • Bullet -> <li>
    - [Link](url) -> <a href="url">
    """
    import re
    
    # Normalize bullet characters
    text = text.replace('•', '*')
    
    # If content already has HTML structure, pass through (markdown already handled it)
    if re.search(r'<(ul|ol|li|p|table)[>\s]', text, re.IGNORECASE):
        return text
    
    # 1. Convert markdown links [text](url) to <a href="url">text</a>
    text = re.sub(
        r'\[(.*?)\]\((.*?)\)', 
        r'<a href="\2" style="color: #3b82f6; text-decoration: underline; font-weight: 600;">\1</a>', 
        text
    )

    # 2. Convert bold/italic markdown into clean <strong> tags
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong style="color: #ffffff; font-size: 15px;">\1</strong>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong style="color: #ffffff; font-size: 14px;">\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em style="color: #cbd5e1;">\1</em>', text)
    
    # 3. Convert bullet points to proper list items
    lines = text.split('\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('* ') or line.startswith('- '):
            if not in_list:
                formatted_lines.append('<ul style="padding-left: 20px; color: #cbd5e1; margin-top: 8px;">')
                in_list = True
            content = line[2:].strip()
            formatted_lines.append(f'<li style="margin-bottom: 4px;">{content}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if line:
                formatted_lines.append(f'<p style="margin-bottom: 12px; line-height: 1.6; color: #cbd5e1;">{line}</p>')
            else:
                formatted_lines.append('<br>')
                
    if in_list:
        formatted_lines.append('</ul>')
        
    result = "\n".join(formatted_lines)
    # Strip any stray square brackets from non-HTML text
    import re as _re
    parts = _re.split(r'(<[^>]+>)', result)
    for i, p in enumerate(parts):
        if not (p.startswith('<') and p.endswith('>')):
            parts[i] = p.replace('[', '').replace(']', '')
    return ''.join(parts)

# ---------------------------------------------------------------------------
# Template-aware attachment selection
# Maps email subject keywords → list of PDF filenames to attach from assets/.
# The hospital teaser replaces Lalit_Huria_Profile.pdf for hospital outreach.
# ---------------------------------------------------------------------------
_HOSPITAL_SUBJECT_MARKER = "Integrated Multi-Site Hospital Platform"
_HOSPITAL_TEASER_FILE    = "eastern_up_hospital_investor_teaser_v5b_investorfriendly (2).pdf"

_TEMPLATE_ATTACHMENT_MAP = {
    "ayush_sir_hospital_draft": [
        "QVSCL Company Profile.pdf",
        _HOSPITAL_TEASER_FILE,
    ],
    "yashika_draft_ai_tech": [],
    "palak_mam_corporate_advisory": [
        "QVSCL Company Profile.pdf",
    ],
    "palak_mam_mna_fundraising": [
        "QVSCL Company Profile.pdf",
        "Lalit_Huria_Profile.pdf",
    ],
    "kajal_mam_qvscl_intro": [],
    "kajal_mam_health_ecosystem": [],
    "kajal_mam_jv": [],
    "kajal_mam_hyphen": [],
    "kajal_mam_agritech": [],
    "vismaya_leadstream": [],
    "yashika_draft_agritech": [],
}

def _get_attachment_files_for_subject(subject: str, template_name: Optional[str] = None) -> list:
    """Return the list of PDF filenames to attach, chosen based on the email subject or template name.
    Checks hardcoded _TEMPLATE_ATTACHMENT_MAP first, then falls back to
    prompts.attachment_file for custom user-uploaded PDFs.
    """
    if template_name and template_name in _TEMPLATE_ATTACHMENT_MAP:
        return _TEMPLATE_ATTACHMENT_MAP[template_name]
    if template_name:
        try:
            from app.database import get_db_connection
            import psycopg2.extras
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                "SELECT attachment_file FROM prompts WHERE name = %s AND prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE",
                (template_name,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row['attachment_file']:
                return [row['attachment_file']]
        except Exception:
            pass
    if subject and _HOSPITAL_SUBJECT_MARKER in subject:
        return ["QVSCL Company Profile.pdf", _HOSPITAL_TEASER_FILE]
    return ["QVSCL Company Profile.pdf", "Lalit_Huria_Profile.pdf"]

def send_email(to_email: str, subject: str, html_content: str, from_email: Optional[str] = None, from_name: Optional[str] = None, attachments: Optional[list] = None, lead_id: Optional[int] = None, is_system_email: bool = False, user_id: Optional[int] = None, cc: Optional[str] = None, thread_id: Optional[str] = None, in_reply_to: Optional[str] = None, template_name: Optional[str] = None) -> bool:
    """Sends an email using Gmail API (if token available) or falls back to Provider/SMTP."""
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
    # Normalize bullet characters for markdown compatibility
    html_content = html_content.replace('•', '*')
    # Convert markdown to HTML for a premium look
    if not html_content.strip().startswith('<'):
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
    # Safety filter: strip any hardcoded qvscl.com unsubscribe links from email body
    import re as _qvscl_re
    html_content = _qvscl_re.sub(
        r'<a\s[^>]*href="[^"]*qvscl\.com[^"]*"[^>]*>.*?</a>',
        '',
        html_content,
        flags=_qvscl_re.IGNORECASE | _qvscl_re.DOTALL
    )
    html_content = _qvscl_re.sub(
        r'<a\s[^>]*href=\'[^\']*qvscl\.com[^\']*\'[^>]*>.*?</a>',
        '',
        html_content,
        flags=_qvscl_re.IGNORECASE | _qvscl_re.DOTALL
    )
    # 1. Prepare default attachments (used by both Gmail and Resend)
    # CRITICAL: Do NOT attach PDFs to follow-up emails! Only attach to the very first email in the sequence.
    # Detect follow-up by thread_id OR by Re: prefix in subject (handles case where thread_id is NULL in DB)
    is_followup = bool(thread_id or in_reply_to or (subject and subject.strip().lower().startswith('re:')))
    
    # Merge any provided attachments with default profile attachments
    merged_attachments = list(attachments) if attachments else []
    if not is_followup:
        asset_dir = Path(__file__).resolve().parent.parent.parent / "assets"
        profile_files = [] if is_vismaya else _get_attachment_files_for_subject(subject, template_name)
        
        logger.info(f"Looking for attachments in: {asset_dir}")
        for filename in profile_files:
            if any(a.get('filename') == filename for a in merged_attachments):
                continue
            path = asset_dir / filename
            if path.exists():
                import base64
                with open(path, "rb") as f:
                    content_bytes = f.read()
                    content_b64 = base64.b64encode(content_bytes).decode('utf-8')
                merged_attachments.append({
                    "content": content_b64,
                    "filename": filename
                })
                logger.info(f"Loaded attachment successfully: {filename}")
            else:
                logger.error(f"Attachment NOT FOUND directly at: {path}")
    else:
        logger.info("Outreach is a follow-up email thread. Default PDF attachments skipped.")
    attachments = merged_attachments

    # 2. Attempt Gmail API Dispatch (Highly Preferred for Outreach)
    if user_id and not is_system_email:
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
                    base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
                    if 'qvscl' in base_url.lower():
                        logger.error(f"BLOCKED: BACKEND_URL contains qvscl.com! Using fallback. Value was: {base_url}")
                        base_url = os.getenv("RENDER_EXTERNAL_URL", "https://lead-backend-g9de.onrender.com")
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

                # Wrap in professional email template for consistent branding
                html_content = f"""
                <div style="font-family: sans-serif; line-height: 1.6; color: #1a202c; font-size: 14px;">
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

                logger.info(f"✅ Gmail API dispatch successful to {to_email} (CC: {cc}) — Message ID: {sent.get('id')}")
                return True, "Success", sent_thread_id, sent_rfc_message_id
            else:
                return False, "Gmail service not initialized. Ensure your Google account is linked with correct permissions.", None, None
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
                except:
                    pass
            
            error_msg = f"Gmail API Error: {str(e)} {error_content}"
            logger.error(f"❌ Gmail API dispatch failed for User {user_id} to {to_email}: {error_msg}\n{error_details}")
            return False, error_msg, None, None

    # 2. Fallback to SMTP/Resend logic
    if user_id and not is_system_email:
        logger.error(f"Gmail API dispatch failed for User {user_id}. ABORTING FALLBACK to system SMTP for personalized outreach.")
        return False, "Gmail API dispatch failed. Personalized outreach requires a working Google connection.", None, None

    provider = os.getenv("EMAIL_PROVIDER", "resend").lower()
    
    if not from_email:
        logger.error(f"ABORTING DISPATCH: No sender email provided for outreach to {to_email}.")
        return False, "Sender email missing.", None, None

    final_from_email = from_email
    final_from_name = from_name or "LeadStream Outreach"
    sender_line = f"{final_from_name} <{final_from_email}>"
    
    if is_system_email:
        final_html = html_content
    else:
        # Process HTML Formatting (Markdown-to-HTML)
        formatted_html = format_outreach_html(html_content)
        
        # Wrap in a clean container
        final_html = f"""
        <div style="font-family: sans-serif; background-color: #0f172a; color: #cbd5e1; padding: 40px; border-radius: 12px; max-width: 600px; margin: auto;">
            {formatted_html}
        </div>
        """
    
    logger.info(f"Targeting dispatch to {to_email} via {provider}. Sender: {sender_line}")

    if provider == "resend":
        try:
            # Re-initialize API key to ensure it is fresh from the environment
            load_dotenv(dotenv_path=env_path, override=True)
            resend_key = os.getenv("RESEND_API_KEY")
            
            if not resend_key:
                logger.error("RESEND_API_KEY is missing from environment.")
                return False, "Resend API key missing.", None, None
            
            # Safe debug: only show prefix to verify key identity
            key_prefix = resend_key[:6] if resend_key else "NONE"
            logger.info(f"Attempting dispatch with Resend Key (prefix: {key_prefix}...)")
            
            resend.api_key = resend_key
            
            params = {
                "from": sender_line,
                "to": to_email,
                "subject": subject,
                "html": final_html,
                "reply_to": from_email
            }
            
            if cc:
                params["cc"] = cc

            if lead_id:
                from app.models.lead import get_or_create_unsubscribe_token
                try:
                    unsub_token = get_or_create_unsubscribe_token(lead_id)
                except Exception:
                    unsub_token = None
                base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
                if 'qvscl' in base_url.lower():
                    logger.error(f"BLOCKED: BACKEND_URL contains qvscl.com! Using fallback. Value was: {base_url}")
                    base_url = os.getenv("RENDER_EXTERNAL_URL", "https://lead-backend-g9de.onrender.com")
                if unsub_token:
                    unsub_url = f"{base_url.rstrip('/')}/unsubscribe?token={unsub_token}"
                else:
                    unsub_url = f"{base_url.rstrip('/')}/api/leads/unsubscribe/{lead_id}"
                logger.info(f"UNSUBSCRIBE URL: Resend List-Unsubscribe URL set to: {unsub_url} (BACKEND_URL={os.getenv('BACKEND_URL', 'NOT SET')})")
                import re as _unsub_re
                _sender_mail = _unsub_re.search(r'[\w.+-]+@[\w.-]+', from_email or '')
                _mailto_addr = _sender_mail.group(0) if _sender_mail else (from_email or '')
                params["headers"] = {
                    "List-Unsubscribe": f"<{unsub_url}>, <mailto:{_mailto_addr}?subject=unsub_{lead_id}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
                }
            
            # Attachments already merged above with profile defaults

            if attachments:
                params["attachments"] = attachments

            sent = resend.Emails.send(params)
            sent_id = getattr(sent, "id", str(sent))
            logger.info(f"Email sent successfully via Resend. ID: {sent_id}")
            return True, "Success", None, None
        except Exception as e:
            logger.error(f"Resend dispatch failed: {str(e)}")
            return False, str(e), None, None
    else:
        success = send_smtp_fallback(to_email, subject, final_html, final_from_email, final_from_name, reply_to=from_email, cc=cc)
        return success, ("SMTP dispatch completed" if success else "SMTP dispatch failed"), None, None

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
                html_content=markdown_to_html(body),
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
                        is_responded = FALSE
                    WHERE id = %s
                """, (subject, subject, new_thread_id, new_rfc_message_id, lead_id))
                conn.commit()
                try:
                    add_activity_log(lead_id, "EMAIL_SENT", f"Scheduled email dispatched automatically", "system")
                except:
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
        from_email=os.getenv("SMTP_USER", admin['email']),
        from_name="LeadStream Intelligence",
        is_system_email=True,
        attachments=report_data.get("attachments")
    )
    return res[0] if isinstance(res, tuple) else res
