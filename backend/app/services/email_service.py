import contextlib
import logging
import os
import re
import ssl
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from the .env file in the current directory
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
logger.info(f"Module initialized with env_path: {env_path}")


def _execute_with_retry(func: Callable, max_retries: int = 3, base_delay: int = 30, max_delay: int = 300, bulk_mode: bool = False) -> Any:
    """
    Execute a function with exponential backoff retry logic.
    Retries up to max_retries times with delays: base_delay, base_delay*2, base_delay*4... (capped at max_delay)
    Handles Gmail API specific errors with longer backoff.
    In bulk_mode: uses much shorter delays (2s base, 30s max) for faster failure recovery.
    """
    import time
    last_error = None

    # Bulk mode uses aggressive short delays
    if bulk_mode:
        multiplier = 2.0
        base_delay = 2  # 2 seconds base
        max_delay = 30  # 30 seconds max
    else:
        multiplier = 2.0

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # Non-retryable errors - only truly permanent auth/permission errors
            non_retryable = [
                "unauthorized",
                "permission denied",
                "forbidden",
                "403",
                "401",
            ]

            should_retry = True
            for nr in non_retryable:
                if nr in error_str:
                    logger.info(f"Non-retryable error on attempt {attempt + 1}: {nr}")
                    should_retry = False
                    break

            # Gmail API specific retryable errors - use longer backoff
            gmail_retryable = [
                "429",
                "rate limit exceeded",
                "dailylimitexceeded",
                "userratelimitexceeded",
                "backend error",
                "internal error",
                "quota exceeded",
                "service unavailable",
                "503",
                "500",
            ]

            gmail_delay_multiplier = 1.0
            for gr in gmail_retryable:
                if gr in error_str:
                    gmail_delay_multiplier = 3.0 if not bulk_mode else 2.0  # Less aggressive in bulk
                    logger.warning(f"Gmail rate limit error detected: {gr}. Using extended backoff.")
                    break

            if attempt < max_retries and should_retry:
                delay = min(base_delay * (multiplier ** attempt) * gmail_delay_multiplier, max_delay)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                break

    raise last_error


def clean_display_filename(filename: str) -> str:
    """Strip the internal `sig_<user_id>_` (and legacy `sig_att_`) prefix from
    signature attachment filenames so recipients and draft UIs see the real
    document name (e.g. `QVSCL_Company_Profile.pdf`) instead of
    `sig_5_QVSCL_Company_Profile..pdf`. DB values are never touched."""
    if not filename:
        return filename
    base = os.path.basename(str(filename))
    # Current upload format: sig_<userid>_<original name>
    m = re.match(r'^sig_\d+_(.+)$', base, re.IGNORECASE)
    if m:
        return m.group(1)
    # Legacy format: sig_att_<original name>
    m = re.match(r'^sig_att_(.+)$', base, re.IGNORECASE)
    if m:
        return m.group(1)
    return base


def _get_signature_attachments(user_id: int | None) -> list:
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
                    # Recipient-facing name — internal sig_<uid>_ prefix hidden.
                    "filename": clean_display_filename(fn)
                })
                logger.info(f"Loaded signature attachment: {fn}")
            else:
                logger.warning(f"Signature attachment NOT FOUND: {fn} at {path}")
        return result
    except Exception as e:
        logger.exception(f"Error fetching signature attachments for user {user_id}: {e}")
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

# Signature font settings (separate from email body)
USER_SIGNATURE_FONTS = {
    2: "Arial, sans-serif",  # Ayush
    3: SANS_SERIF_FONT,      # Kajal
    4: SANS_SERIF_FONT,      # Yashika
    5: SANS_SERIF_FONT,      # Palak
}
DEFAULT_SIGNATURE_FONT = SANS_SERIF_FONT

USER_SIGNATURE_FONT_SIZES = {
    2: "13px",  # Ayush
    3: "11px",  # Kajal
    4: "12px",  # Yashika
    5: "11px",  # Palak
}
DEFAULT_SIGNATURE_FONT_SIZE = "13px"


def get_user_email_font(user_id) -> str:
    """Resolve the preferred email font for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    # First check database for user's custom font setting
    if uid:
        try:
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT email_font FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row.get('email_font'):
                return row['email_font']
            else:
                logger.warning(f"get_user_email_font: No email_font found for user {uid}")
        except Exception as e:
            logger.exception(f"get_user_email_font: DB error for user {uid}: {repr(e)}")
            logger.exception(traceback.format_exc())
    # Fall back to hardcoded dictionary
    return USER_EMAIL_FONTS.get(uid, DEFAULT_EMAIL_FONT)


def get_user_email_font_size(user_id) -> str:
    """Resolve the preferred email font size (px string) for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    # First check database for user's custom font size setting
    if uid:
        try:
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT email_font_size FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row.get('email_font_size'):
                return row['email_font_size']
            else:
                logger.warning(f"get_user_email_font_size: No email_font_size found for user {uid}")
        except Exception as e:
            logger.exception(f"get_user_email_font_size: DB error for user {uid}: {repr(e)}")
            logger.exception(traceback.format_exc())
    # Fall back to hardcoded dictionary
    return USER_EMAIL_FONT_SIZES.get(uid, DEFAULT_EMAIL_FONT_SIZE)


def get_user_signature_font(user_id) -> str:
    """Resolve the preferred signature font for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    # First check database for user's custom font setting
    if uid:
        try:
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT signature_font FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row.get('signature_font'):
                return row['signature_font']
            else:
                logger.warning(f"get_user_signature_font: No signature_font found for user {uid}")
        except Exception as e:
            logger.exception(f"get_user_signature_font: DB error for user {uid}: {repr(e)}")
            logger.exception(traceback.format_exc())
    # Fall back to hardcoded dictionary
    return USER_SIGNATURE_FONTS.get(uid, DEFAULT_SIGNATURE_FONT)


def get_user_signature_font_size(user_id) -> str:
    """Resolve the preferred signature font size (px string) for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    # First check database for user's custom font size setting
    if uid:
        try:
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT signature_font_size FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row.get('signature_font_size'):
                return row['signature_font_size']
            else:
                logger.warning(f"get_user_signature_font_size: No signature_font_size found for user {uid}")
        except Exception as e:
            logger.exception(f"get_user_signature_font_size: DB error for user {uid}: {repr(e)}")
            logger.exception(traceback.format_exc())
    # Fall back to hardcoded dictionary
    return USER_SIGNATURE_FONT_SIZES.get(uid, DEFAULT_SIGNATURE_FONT_SIZE)


def get_user_image_width(user_id) -> str:
    """Resolve the preferred image width for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    if uid:
        try:
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT image_width FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row.get('image_width'):
                return row['image_width']
        except Exception as e:
            logger.exception(f"get_user_image_width: DB error for user {uid}: {repr(e)}")
    return "400px"


def get_user_image_height(user_id) -> str:
    """Resolve the preferred image height for a user id."""
    try:
        uid = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        uid = None
    if uid:
        try:
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT image_height FROM users WHERE id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row.get('image_height'):
                return row['image_height']
        except Exception as e:
            logger.exception(f"get_user_image_height: DB error for user {uid}: {repr(e)}")
    return "auto"


def strip_old_unsubscribe_links(html_content: str) -> str:
    """Remove legacy unsubscribe footers/sentences and leftover
    'Click here to unsubscribe' links from content. The fresh footer is
    appended by the caller afterwards, so the final email has exactly one."""
    import re as _us
    # Old footer sentence that may linger in previously-saved drafts.
    html_content = html_content.replace(
        "You're receiving this because you interacted with LeadStream.", ""
    )
    # Remove the whole legacy footer block (hr + sentence paragraph) if present.
    # Both the hr margin and the paragraph font-size anchor the match to the
    # footer's exact styles, so body content is never touched.
    html_content = _us.sub(
        r'<hr\s[^>]*margin:\s*20px\s+0\s+10px\s+0[^>]*>\s*'
        r'<p\s[^>]*font-size:\s*12px[^>]*>.*?</p>',
        '', html_content, flags=_us.DOTALL | _us.IGNORECASE
    )
    # Remove any leftover unsubscribe links — the fresh footer is appended after.
    html_content = _us.sub(
        r'<a\s[^>]*>Click here to unsubscribe</a>', '', html_content,
        flags=_us.IGNORECASE
    )
    # Legacy markdown-form links (e.g. [Click here to unsubscribe](old-url)) that
    # survive conversion when the body is already rich HTML and the markdown
    # branch is skipped. Removing them keeps exactly one footer in the final mail.
    html_content = _us.sub(
        r'\[Click here to unsubscribe\]\([^)]*\)', '', html_content,
        flags=_us.IGNORECASE
    )
    # Drop now-empty footer-style paragraphs left behind (scoped to the footer's
    # font-size so legitimate body paragraphs are never removed).
    return _us.sub(
        r'<p\s[^>]*font-size:\s*12px[^>]*>\s*</p>', '', html_content,
        flags=_us.IGNORECASE
    )


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
        logger.exception(f"Failed to get unsubscribe token for lead {lead_id}: {_ut_err}")
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
<a href="{_uurl}" style="color:#888;text-decoration:underline">Click here to unsubscribe</a>
</p>"""

def send_email(to_email: str, subject: str, html_content: str, from_email: str | None = None, from_name: str | None = None, attachments: list | None = None, lead_id: int | None = None, is_system_email: bool = False, user_id: int | None = None, cc: str | None = None, thread_id: str | None = None, in_reply_to: str | None = None, template_name: str | None = None, bulk_mode: bool = False) -> tuple:
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

    # 4. Append unsubscribe footer (strip above removed old ones, so append fresh)
    html_content += build_unsubscribe_footer(lead_id)

    # 2. Attempt Gmail API Dispatch (Gmail is the only dispatch method now)
    if user_id:
        try:
            import base64
            from email.mime.application import MIMEApplication
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            from app.services.google_service import get_gmail_service

            service = None
            try:
                # Local normalization to avoid circular imports
                uid_str = str(user_id) if user_id else "1"
                uid_t = uid_str if uid_str.isdigit() else "1"

                service = get_gmail_service(int(uid_t))
                if not service:
                    logger.warning(f"No Gmail service found for user {uid_t}. personalized dispatch skipped.")
            except Exception as e:
                logger.exception(f"Error building Gmail service for user {user_id}: {e}")
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
                        logger.exception(f"Failed to dynamically heal thread from Gmail: {he}")

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
                # in the saved draft from overriding the wrapper. TABLES and the
                # SIGNATURE BLOCK are EXEMPT: their font-sizes (e.g. a 9pt header row,
                # or the 8px disclaimer line set in the signature editor) are part of
                # the design and must survive to the sent email.
                import re as _fs_re

                def _strip_fontsize_preserving_design(html: str) -> str:
                    # Regions to keep untouched: tables + signature container div
                    protected = []

                    # 1) Tables
                    for _m in _fs_re.finditer(r'<table[^>]*>.*?</table>', html, flags=_fs_re.DOTALL | _fs_re.IGNORECASE):
                        protected.append((_m.start(), _m.end()))

                    # 2) Signature container — markdown_to_html wraps the signature
                    # in <div style="...border-top: 1px solid #f0f0f0...">...</div>.
                    # It can contain nested <div>s (empty-line spacers, legal blocks),
                    # so find the matching close with a depth count.
                    _sig_open = _fs_re.compile(
                        r'<div[^>]*border-top:\s*1px\s+solid\s+#f0f0f0[^>]*>',
                        _fs_re.IGNORECASE,
                    )
                    for _m in _sig_open.finditer(html):
                        _depth = 1
                        _i = _m.end()
                        while _i < len(html) and _depth > 0:
                            _o = html.find('<div', _i)
                            _c = html.find('</div', _i)
                            if _c == -1:
                                break
                            if _o != -1 and _o < _c:
                                _depth += 1
                                _i = _o + 4
                            else:
                                _depth -= 1
                                _i = _c + 5
                        if _depth == 0:
                            protected.append((_m.start(), _i))

                    # Strip font-size only OUTSIDE the protected regions.
                    # Merge overlapping/adjacent ranges first (e.g. a <table>
                    # inside the signature container) so content is never emitted
                    # twice.
                    protected.sort()
                    _merged = []
                    for (_s, _e) in protected:
                        if _merged and _s <= _merged[-1][1]:
                            _merged[-1] = (_merged[-1][0], max(_merged[-1][1], _e))
                        else:
                            _merged.append((_s, _e))
                    _out = []
                    _pos = 0
                    for (_s, _e) in _merged:
                        _out.append(_fs_re.sub(r'font-size\s*:\s*[^;]+;?\s*', '', html[_pos:_s]))
                        _out.append(html[_s:_e])
                        _pos = _e
                    _out.append(_fs_re.sub(r'font-size\s*:\s*[^;]+;?\s*', '', html[_pos:]))
                    return ''.join(_out)

                html_content = _strip_fontsize_preserving_design(html_content)

                # Wrap in clean email template for professional appearance in Gmail
                email_font = get_user_email_font(user_id)
                email_font_size = get_user_email_font_size(user_id)

                # Extract editor line-height from data-lh / data-lh-table wrappers
                import re as _re_lh
                _body_lh = "1.6"
                _table_lh = "1.2"
                _wrapper_match = _re_lh.match(r'<div\s+([^>]+)>', html_content, _re_lh.IGNORECASE)
                if _wrapper_match:
                    _wrapper_attrs = _wrapper_match.group(1)
                    _lh_attr = _re_lh.search(r'data-lh="([^"]+)"', _wrapper_attrs, _re_lh.IGNORECASE)
                    _tlh_attr = _re_lh.search(r'data-lh-table="([^"]+)"', _wrapper_attrs, _re_lh.IGNORECASE)
                    if _lh_attr:
                        _body_lh = _lh_attr.group(1)
                    if _tlh_attr:
                        _table_lh = _tlh_attr.group(1)
                    elif _lh_attr:
                        _table_lh = _body_lh
                    html_content = _re_lh.sub(r'^<div\s+[^>]*>\s*', '', html_content, count=1, flags=_re_lh.IGNORECASE)
                    html_content = _re_lh.sub(r'\s*</div>\s*$', '', html_content)

                html_content = f"""
                <div style="font-family: {email_font}; line-height: {_body_lh}; color: #333333; font-size: {email_font_size};">
                    {html_content}
                </div>
                """

                # Apply table line-height to all table elements that don't already have it
                _tlh_style = f"line-height:{_table_lh};"
                def _ensure_table_lh(m):
                    tag_name = m.group(1)
                    rest = m.group(2) or ''
                    closing = m.group(3) or ''
                    if 'line-height' in rest.lower():
                        return m.group(0)  # already has line-height, skip
                    if 'style=' in rest.lower():
                        prefix = 'style="'
                        idx = rest.lower().find('style="')
                        if idx >= 0:
                            after = rest[idx + len(prefix):]
                            new_rest = rest[:idx] + prefix + _tlh_style + after
                            return '<' + tag_name + new_rest + closing
                    return '<' + tag_name + ' style="' + _tlh_style + '"' + rest + closing
                html_content = _re_lh.sub(r'<(table|th|td)((?:\s[^>]*)?)(/?)>', _ensure_table_lh, html_content, flags=_re_lh.IGNORECASE)

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
                            logger.exception(f"Failed to attach file {attachment.get('filename')}: {e}")

                raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

                # Build the send body — add threadId if this is a reply
                send_body = {'raw': raw_message}
                if thread_id:
                    send_body['threadId'] = thread_id
                logger.info(f"📧 send_email: thread_id={thread_id!r}, in_reply_to={in_reply_to!r}, lead_id={lead_id}, to={clean_to}, subject={clean_subject}")

                # Gmail API send with retry logic (3 retries, exponential backoff)
                def _send_gmail():
                    return service.users().messages().send(userId='me', body=send_body).execute()

                try:
                    sent = _execute_with_retry(_send_gmail, bulk_mode=bulk_mode)
                except ssl.SSLError as ssl_err:
                    logger.warning(f"SSL error after retries for user {user_id}: {ssl_err}. Invalidating cache and final retry...")
                    from app.services.google_service import invalidate_gmail_service_cache
                    invalidate_gmail_service_cache(int(uid_t))
                    service = get_gmail_service(int(uid_t))
                    if service:
                        sent = _execute_with_retry(
                            lambda: service.users().messages().send(userId='me', body=send_body).execute(),
                            bulk_mode=bulk_mode
                        )
                    else:
                        raise
                except Exception as api_err:
                    err_str = str(api_err)
                    err_lower = err_str.lower()

                    # Thread not found - retry without thread_id
                    if '404' in err_str and 'not found' in err_lower and thread_id:
                        logger.warning(f"Thread {thread_id} not found in Gmail — retrying without thread_id")
                        send_body.pop('threadId', None)
                        sent = _execute_with_retry(
                            lambda: service.users().messages().send(userId='me', body=send_body).execute(),
                            bulk_mode=bulk_mode
                        )

                    # Gmail API specific retryable errors - let _execute_with_retry handle retries
                    # These are now retried automatically via _execute_with_retry's gmail_retryable list
                    # Just re-raise to let the retry logic handle it
                    elif any(x in err_lower for x in ['429', 'rate limit', 'dailylimit', 'userratelimit', 'quota exceeded', '503', '500', 'backend error', 'internal error', 'service unavailable']):
                        logger.warning(f"Gmail retryable error (will retry): {err_str}")
                        raise

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
            traceback.format_exc()
            if hasattr(e, 'content'):
                e.content.decode() if hasattr(e.content, 'decode') else str(e.content)

            # Invalidate cached service on SSL errors so next call gets a fresh connection
            if isinstance(e, ssl.SSLError):
                try:
                    from app.services.google_service import invalidate_gmail_service_cache
                    invalidate_gmail_service_cache(int(uid_t))
                except Exception:
                    pass

            logger.exception(f"❌ Gmail API dispatch failed for User {user_id} to {to_email}: {str(e)}")
            logger.exception(traceback.format_exc())
            return False, f"Gmail API error: {str(e)}", None, None

    # No SMTP/Resend fallback — Gmail API is the only dispatch method for outreach
    logger.error(f"Cannot send email to {to_email}: No Gmail connection available for User {user_id}.")
    return False, "Gmail not connected. Please link your Google account in Settings.", None, None

def schedule_drip_batch(lead_ids: list, uid, grace_minutes: int = None):
    """
    Schedules a batch of leads for drip-sending:
      - First slot: now + grace (default 30 min), rolled to the next working window
      - Each subsequent email: +drip_interval_minutes with random jitter
      - Every slot rolled forward past blackouts (7PM-9AM IST) and weekends

    Atomic per-row: only rows still in PENDING_APPROVAL are scheduled, so a
    concurrent manual reject/edit always wins over auto-scheduling.

    Returns dict: {scheduled, skipped, first_send, last_send}
    """
    import random as _random
    from datetime import datetime, timedelta

    from app.core.pipeline.scheduler import get_scheduler_config
    from app.database import get_db_connection
    from app.models.lead import add_activity_log

    cfg = get_scheduler_config()
    grace = grace_minutes if grace_minutes is not None else cfg.drip_grace_minutes
    uid_int = int(uid) if uid and str(uid).isdigit() else None
    if not lead_ids:
        return {"scheduled": 0, "skipped": 0}

    conn = get_db_connection()
    cur = conn.cursor()
    scheduled = 0
    skipped = 0
    try:
        slot = datetime.now() + timedelta(minutes=grace)
        first_send = last_send = None
        for i, lid in enumerate(lead_ids):
            if i > 0:
                offset = cfg.drip_interval_minutes * 60 + _random.randint(0, max(cfg.drip_jitter_seconds, 1))
                slot = slot + timedelta(seconds=offset)
            slot = cfg.next_working_time(slot)

            cur.execute("""
                UPDATE leads_raw
                SET email_status = 'SCHEDULED',
                    scheduled_at = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND user_id = %s
                  AND email_status IN ('PENDING_APPROVAL', 'APPROVED')
            """, (slot, lid, uid_int))
            if cur.rowcount > 0:
                scheduled += 1
                if first_send is None:
                    first_send = slot
                last_send = slot
                with contextlib.suppress(Exception):
                    add_activity_log(lid, "EMAIL_SCHEDULED",
                                     f"Drip scheduled for {slot.strftime('%a %d %b %I:%M %p')} IST (position {i+1})",
                                     "system")
            else:
                skipped += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.exception(f"schedule_drip_batch failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    # Refresh review-queue caches — these drafts left PENDING_APPROVAL
    with contextlib.suppress(Exception):
        invalidate_pending_drafts_cache(str(uid) if uid else None)

    return {
        "scheduled": scheduled,
        "skipped": skipped,
        "first_send": first_send.isoformat() if first_send else None,
        "last_send": last_send.isoformat() if last_send else None,
    }


def process_auto_pilot_sweep():
    """
    Auto-Pilot sweep (runs ~every 5 min from the scheduler):
    For each user with auto_pilot_drafts enabled AND a connected Gmail account,
    finds their review-queue drafts that have been pending for at least the
    grace window (30 min) and drip-schedules them automatically.

    Eligibility mirrors the dispatcher's safety filters so nothing gets
    scheduled that could never be sent.
    """
    try:
        from app.core.pipeline.scheduler import get_scheduler_config
        from app.database import get_db_connection

        cfg = get_scheduler_config()

        # Skip auto-pilot on weekends/outside working hours
        if not cfg.is_working_hours_now():
            return {"scheduled": 0, "users": 0, "skipped": "outside working hours"}

        grace_minutes = cfg.drip_grace_minutes

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM users
            WHERE COALESCE(auto_pilot_drafts, FALSE) = TRUE
              AND google_refresh_token IS NOT NULL
              AND is_active = TRUE
        """)
        pilot_users = [list(r.values())[0] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()

        if not pilot_users:
            return {"scheduled": 0, "users": 0}

        total_scheduled = 0
        for uid in pilot_users:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(f"""
                    SELECT lr.id
                    FROM leads_raw lr
                    WHERE lr.user_id = %s
                      AND lr.email_status = 'PENDING_APPROVAL'
                      AND lr.email_draft IS NOT NULL
                      AND lr.updated_at <= NOW() - INTERVAL '{int(grace_minutes)} minutes'
                      AND (lr.email_opt_in IS NULL OR lr.email_opt_in = TRUE)
                      AND (lr.is_unsubscribed IS NULL OR lr.is_unsubscribed = FALSE)
                      AND lr.email NOT IN (SELECT email FROM unsubscribe_list)
                    ORDER BY lr.id
                    LIMIT 200
                """, (uid,))
                lead_ids = [list(r.values())[0] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
                cur.close()
                conn.close()

                if not lead_ids:
                    continue

                result = schedule_drip_batch(lead_ids, uid)
                total_scheduled += result.get("scheduled", 0)
                if result.get("scheduled"):
                    logger.info(
                        f"Auto-Pilot: scheduled {result['scheduled']} drafts for user {uid} "
                        f"(first: {result.get('first_send')})"
                    )
            except Exception as ue:
                logger.exception(f"Auto-Pilot sweep failed for user {uid}: {ue}")

        return {"scheduled": total_scheduled, "users": len(pilot_users)}
    except Exception as e:
        logger.exception(f"Auto-Pilot sweep error: {e}")
        return {"scheduled": 0, "error": str(e)}


def _cleanup_gmail_draft(user_id, gmail_draft_id, lead_id, cur=None, conn=None):
    """Delete a lead's Gmail draft after it has been (or fails to be) sent, so
    it doesn't linger as an orphaned draft in the user's Gmail. Best-effort."""
    if not gmail_draft_id:
        return
    try:
        from app.services.google_service import delete_gmail_draft
        delete_gmail_draft(int(user_id) if user_id else 0, gmail_draft_id)
    except Exception as e:
        logger.warning(f"Could not delete Gmail draft {gmail_draft_id} for lead {lead_id}: {e}")
    try:
        if cur is not None:
            cur.execute("UPDATE leads_raw SET gmail_draft_id = NULL WHERE id = %s", (lead_id,))
            if conn is not None:
                conn.commit()
    except Exception:
        pass


def check_scheduled_emails():
    """
    Checks the database for any emails in 'SCHEDULED' state where
    scheduled_at <= NOW(). Attempts to send them and updates state to SENT.

    Hardened with drip-safety guards:
      1. Working-hours blackout (9AM-7PM IST, Mon-Fri) — due emails simply wait
      2. Cooldown: >=N sends in the rolling window pauses this cycle
      3. Per-cycle cap on dispatches
      4. Daily-limit exceeded → lead pushed to next working day 9AM
    """
    try:
        import psycopg2.extras
        from app.core.pipeline.scheduler import get_scheduler_config
        from app.database import get_db_connection
        from app.models.lead import add_activity_log
        from app.utils.auth_helpers import check_daily_email_limit

        cfg = get_scheduler_config()

        # Guard 1: working-hours blackout — scheduled items just wait here
        if not cfg.is_working_hours_now():
            return

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Guard 2: rolling-window cooldown — any recent outreach counts
        # (manual + drip) so total volume stays human-like.
        cur.execute(f"""
            SELECT COUNT(*) FROM leads_raw
            WHERE email_status = 'SENT'
              AND updated_at > NOW() - INTERVAL '{int(cfg.cooldown_window_minutes)} minutes'
        """)
        recent_sends = cur.fetchone()[0]
        if recent_sends >= cfg.cooldown_every_n_emails:
            logger.info(
                f"Drip cooldown active: {recent_sends} sends in last {cfg.cooldown_window_minutes} min "
                f"(>= {cfg.cooldown_every_n_emails}). Cycle skipped."
            )
            cur.close()
            conn.close()
            return

        # Guard 3: per-cycle cap
        fetch_limit = max(cfg.scheduled_max_per_cycle, 1)

        cur.execute("""
            SELECT l.id, l.email, l.email_draft, l.cc_email, l.user_id, l.draft_template_used,
                   u.email as sender_email, u.full_name, u.username
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            WHERE l.email_status = 'SCHEDULED'
              AND (l.scheduled_at AT TIME ZONE 'Asia/Kolkata') <= NOW()
              AND COALESCE(l.is_responded, FALSE) = FALSE
              AND COALESCE(l.followup_status, '') != 'STOPPED'
              AND (l.email_opt_in IS NULL OR l.email_opt_in = TRUE)
              AND (l.is_unsubscribed IS NULL OR l.is_unsubscribed = FALSE)
              AND l.email NOT IN (SELECT email FROM unsubscribe_list)
            ORDER BY l.scheduled_at ASC
            LIMIT %s
        """, (fetch_limit,))

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

            # Guard 4: daily-limit exceeded → push this lead to next working day 9AM
            if not check_daily_email_limit(str(lead['user_id']) if lead['user_id'] else None, 1):
                from datetime import timedelta as _td
                push_to = cfg.next_working_time(
                    (datetime.now() + _td(days=1)).replace(hour=cfg.working_hours_start, minute=0, second=0)
                )
                cur.execute("""
                    UPDATE leads_raw SET scheduled_at = %s, updated_at = NOW()
                    WHERE id = %s
                """, (push_to, lead_id))
                conn.commit()
                logger.info(f"Daily limit reached for user {lead['user_id']} — lead {lead_id} pushed to {push_to}")
                continue

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
            from app.services.email_service import get_user_image_height, get_user_image_width
            success, error_msg, new_thread_id, new_rfc_message_id = send_email(
                to_email=to_email,
                subject=subject,
                html_content=markdown_to_html(
                    body,
                    font_family=get_user_email_font(user_id),
                    font_size=get_user_email_font_size(user_id),
                    image_width=get_user_image_width(user_id),
                    image_height=get_user_image_height(user_id)
                ),
                from_email=sender_email,
                from_name=sender_name,
                lead_id=lead_id,
                user_id=user_id,
                cc=cc_email,
                template_name=lead.get('draft_template_used')
            )

            gmail_draft_id = lead.get('gmail_draft_id')
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
                        pipeline_state = 'FOLLOWUP_ACTIVE',
                        is_responded = FALSE,
                        replied_at = NULL
                    WHERE id = %s
                """, (subject, subject, new_thread_id, new_rfc_message_id, lead_id))
                conn.commit()
                with contextlib.suppress(Exception):
                    add_activity_log(lead_id, "EMAIL_SENT", "Scheduled email dispatched automatically", "system")
                _cleanup_gmail_draft(lead['user_id'], gmail_draft_id, lead_id, cur, conn)
            else:
                logger.error(f"Failed to send scheduled email {lead_id} to {to_email}")
                # Mark FAILED so it doesn't retry forever, and remove the stale
                # Gmail draft so it doesn't linger in the user's Gmail.
                try:
                    cur.execute("""
                        UPDATE leads_raw
                        SET email_status = 'FAILED',
                            gmail_draft_id = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (lead_id,))
                    conn.commit()
                except Exception:
                    pass
                _cleanup_gmail_draft(lead['user_id'], gmail_draft_id, lead_id, cur, conn)

        cur.close()
        conn.close()
    except Exception as e:
        logger.exception(f"Error in check_scheduled_emails: {str(e)}")
def send_admin_report(to_email: str, report_data: dict) -> bool:
    """
    Formulates and sends a high-level MIS (Management Information System) report
    to the administrator, detailing user productivity and system signals.
    """
    user_stats = report_data.get("user_stats", [])
    report_data.get("recent_logs", [])
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
