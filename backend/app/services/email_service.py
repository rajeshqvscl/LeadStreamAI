import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from the .env file in the current directory
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

logger = logging.getLogger(__name__)

def send_email(to_email, subject, html_content, attachments=None):
    """Generic SMTP sender with environment-based configuration."""
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    sender_email = os.getenv("SENDER_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP credentials missing in .env. Skipping email dispatch.")
        # Fallback: Print to console for visibility during dev
        print(f"--- [DRY RUN] EMAIL TO: {to_email} ---")
        print(f"Subject: {subject}")
        print("Content (HTML): [Omitted from console]")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"LeadStream AI <{sender_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(html_content, 'html'))

        # Add default system attachments if they exist
        assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"
        default_files = ["QVSCL Company Profile.pdf", "Lalit_Huria_Profile.pdf"]
        
        for filename in default_files:
            file_path = assets_dir / filename
            if file_path.exists():
                with open(file_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=filename)
                    part['Content-Disposition'] = f'attachment; filename="{filename}"'
                    msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def send_admin_report(admin_email, report_data):
    """Formats and sends the high-end system activity report."""
    stats = report_data.get('user_stats', [])
    logs = report_data.get('recent_logs', [])
    env = report_data.get('environment', 'Production')
    
    # Calculate global aggregates
    total_leads = sum(s.get('leads_count', 0) for s in stats)
    total_sent = sum(s.get('sent_count', 0) for s in stats)
    
    subject = f"🚀 System Pulse: {datetime.now().strftime('%Y-%m-%d')} | {env}"
    
    # Premium HTML Template
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #1e293b; color: white; padding: 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">Admin Command Center</h1>
                <p style="margin: 5px 0 0; opacity: 0.8; font-size: 14px;">System Activity Report</p>
            </div>
            
            <div style="padding: 30px;">
                <h2 style="font-size: 18px; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-bottom: 20px;">Global Summary (Last 24h)</h2>
                <div style="display: flex; gap: 20px; margin-bottom: 30px;">
                    <div style="background: #eff6ff; padding: 20px; border-radius: 8px; flex: 1; text-align: center;">
                        <p style="margin: 0; font-size: 12px; color: #3b82f6; font-weight: bold;">LEADS</p>
                        <p style="margin: 5px 0 0; font-size: 24px; font-weight: black;">{total_leads}</p>
                    </div>
                    <div style="background: #f5f3ff; padding: 20px; border-radius: 8px; flex: 1; text-align: center;">
                        <p style="margin: 0; font-size: 12px; color: #8b5cf6; font-weight: bold;">OUTREACH</p>
                        <p style="margin: 5px 0 0; font-size: 24px; font-weight: black;">{total_sent}</p>
                    </div>
                </div>

                <h2 style="font-size: 16px; margin-bottom: 15px;">Personnel Activity</h2>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
                    <thead>
                        <tr style="text-align: left; background: #f8fafc;">
                            <th style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 12px;">Agent</th>
                            <th style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 12px; text-align: center;">Leads</th>
                            <th style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 12px; text-align: center;">Sent</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for s in stats:
        html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; font-size: 14px;">{s['username']}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; font-size: 14px; text-align: center;">{s['leads_count']}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; font-size: 14px; text-align: center;">{s['sent_count']}</td>
            </tr>
        """
        
    html += """
                    </tbody>
                </table>

                <h2 style="font-size: 16px; margin-bottom: 15px;">Recent System Interactions</h2>
                <div style="background: #fafafa; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 12px;">
    """
    
    for log in logs:
        html += f"<div>[{log['created_at'].split('T')[1][:5]}] {log['username']} - {log['action']}</div>"
        
    html += """
                </div>
            </div>
            
            <div style="background: #f8fafc; padding: 20px; text-align: center; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0; font-size: 11px; color: #94a3b8;">Sent via LeadStream AI Dashboard - Automated System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(admin_email, subject, html)
