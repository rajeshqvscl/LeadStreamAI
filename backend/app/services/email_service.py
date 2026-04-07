import os
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

def send_smtp_fallback(to_email: str, subject: str, html_content: str, from_email: str, from_name: str) -> bool:
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
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent successfully via SMTP to {to_email}")
        return True
    except Exception as e:
        logger.error(f"SMTP Dispatch Error: {str(e)}")
        return False

def format_outreach_html(text: str) -> str:
    """
    Converts markdown-style bold and bullets into clean HTML.
    Specifically targets **Heading** -> <strong>Heading</strong>
    and • Bullet -> <li>Bullet</li>
    """
    import re
    # Convert bold **text** to <strong>text</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong style="color: #ffffff; font-size: 14px;">\1</strong>', text)
    
    # Convert bullet points • text to list items
    lines = text.split('\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('•') or line.startswith('* '):
            if not in_list:
                formatted_lines.append('<ul style="padding-left: 20px; color: #cbd5e1; margin-top: 8px;">')
                in_list = True
            content = line.lstrip('•* ').strip()
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
        
    return "\n".join(formatted_lines)

def send_email(to_email: str, subject: str, html_content: str, from_email: Optional[str] = None, from_name: Optional[str] = None, attachments: Optional[list] = None) -> bool:
    """
    Sends an email using Resend (production) or SMTP (fallback).
    Strictly follows dynamic identity.
    """
    provider = os.getenv("EMAIL_PROVIDER", "resend").lower()
    
    if not from_email:
        logger.error(f"ABORTING DISPATCH: No sender email provided for outreach to {to_email}.")
        return False

    final_from_email = from_email
    final_from_name = from_name or "LeadStream Outreach"
    sender_line = f"{final_from_name} <{final_from_email}>"
    
    # Process HTML Formatting (Markdown-to-HTML)
    formatted_html = format_outreach_html(html_content)
    
    # Wrap in a clean container
    final_html = f"""
    <div style="font-family: 'Inter', sans-serif; background-color: #0f172a; color: #cbd5e1; padding: 40px; border-radius: 12px; max-width: 600px; margin: auto;">
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
                return False
            
            # Safe debug: only show prefix to verify key identity
            key_prefix = resend_key[:6] if resend_key else "NONE"
            logger.info(f"Attempting dispatch with Resend Key (prefix: {key_prefix}...)")
            
            resend.api_key = resend_key
            
            params = {
                "from": sender_line,
                "to": to_email,
                "subject": subject,
                "html": final_html,
            }
            
            # Attach default profiles from assets
            if not attachments:
                attachments = []
                # Correct path: email_service.py is in backend/app/services/
                # .parent = backend/app/services/
                # .parent.parent = backend/app/
                # .parent.parent.parent = backend/
                asset_dir = Path(__file__).resolve().parent.parent.parent / "assets"
                profile_files = ["QVSCL Company Profile.pdf", "Lalit_Huria_Profile.pdf"]
                
                logger.info(f"Looking for attachments in: {asset_dir}")
                
                for filename in profile_files:
                    path = asset_dir / filename
                    if path.exists():
                        import base64
                        with open(path, "rb") as f:
                            content_bytes = f.read()
                            content_b64 = base64.b64encode(content_bytes).decode()
                        attachments.append({
                            "content": content_b64,
                            "filename": filename
                        })
                        logger.info(f"Attached successfully: {filename}")
                    else:
                        logger.error(f"Attachment NOT FOUND directly at: {path}")

            if attachments:
                params["attachments"] = attachments

            sent = resend.Emails.send(params)
            sent_id = getattr(sent, "id", str(sent))
            logger.info(f"Email sent successfully via Resend. ID: {sent_id}")
            return True
        except Exception as e:
            logger.error(f"Resend dispatch failed: {str(e)}")
            return False
    else:
        return send_smtp_fallback(to_email, subject, final_html, final_from_email, final_from_name)
