from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from app.database import get_db_connection
import psycopg2
import psycopg2.extras
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def normalize_user_id(user_id: Optional[str]) -> str:
    """Normalizes the user ID from the header to a valid database ID."""
    if not user_id or user_id.strip() == "" or user_id.lower() == "admin":
        return "1"
    return user_id

@router.get("/admin/stats")
async def get_admin_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns global metrics for the Admin Command Center (Real Data)."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Simple Admin Check
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()

        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized: Admin access required")
            
        cur.execute("SELECT COUNT(*) as total FROM leads_raw")
        total_leads = cur.fetchone()['total'] or 0
        
        cur.execute("SELECT COUNT(*) as active FROM users WHERE is_active = TRUE")
        active_users = cur.fetchone()['active'] or 0
        
        try:
            cur.execute("SELECT COUNT(*) as active_campaigns FROM campaigns WHERE status IN ('ACTIVE', 'active')")
            active_campaigns = cur.fetchone()['active_campaigns'] or 0
        except psycopg2.Error:
            active_campaigns = 0
            conn.rollback()
        
        cur.execute("SELECT COUNT(*) as sent_total FROM activity_log WHERE action IN ('SENT', 'EMAIL_SENT', 'BULK_DRAFT_GENERATE')")
        sent_total = cur.fetchone()['sent_total'] or 0
        
        return {
            "total_leads": total_leads,
            "active_users": active_users,
            "active_campaigns": active_campaigns,
            "sent_total": sent_total
        }
    finally:
        cur.close()
        conn.close()

@router.get("/admin/velocity")
async def get_admin_velocity(
    period: str = Query("daily", pattern="^(daily|weekly|monthly|quarterly)$"),
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """Returns time-series data for system growth velocity using REAL database counts."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Simple Admin Check
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()
        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized")
            
        today = datetime.now()
        velocity_data = []
        
        # Determine aggregate intervals and ranges
        if period == "daily":
            cur.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM leads_raw 
                WHERE created_at > CURRENT_DATE - INTERVAL '6 days'
                GROUP BY 1 ORDER BY 1
            """)
            leads_rows = {row['date']: row['count'] for row in cur.fetchall()}
            
            cur.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM activity_log 
                WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT', 'EMAIL_SENT')
                AND created_at > CURRENT_DATE - INTERVAL '6 days'
                GROUP BY 1 ORDER BY 1
            """)
            activity_rows = {row['date']: row['count'] for row in cur.fetchall()}

            for i in range(7):
                d = (today - timedelta(days=6-i)).date()
                velocity_data.append({
                    "day": d.strftime("%a"),
                    "leads": leads_rows.get(d, 0),
                    "emails": activity_rows.get(d, 0)
                })

        elif period == "weekly":
            # Last 8 weeks
            for i in range(8):
                start_date = today - timedelta(weeks=8-i)
                end_date = today - timedelta(weeks=7-i)
                
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at >= %s AND created_at < %s", (start_date, end_date))
                l_count = cur.fetchone()[0] or 0
                
                cur.execute("SELECT COUNT(*) FROM activity_log WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT') AND created_at >= %s AND created_at < %s", (start_date, end_date))
                e_count = cur.fetchone()[0] or 0
                
                velocity_data.append({
                    "day": f"Wk {i+1}",
                    "leads": l_count,
                    "emails": e_count
                })

        elif period == "monthly":
            # Real SQL for last 4 months
            for i in range(4):
                month_start = (today.replace(day=1) - timedelta(days=120 - (30*i))).replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1)
                
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at >= %s AND created_at < %s", (month_start, month_end))
                l_count = cur.fetchone()[0] or 0
                
                cur.execute("SELECT COUNT(*) FROM activity_log WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT') AND created_at >= %s AND created_at < %s", (month_start, month_end))
                e_count = cur.fetchone()[0] or 0
                
                velocity_data.append({
                    "day": month_start.strftime("%b"),
                    "leads": l_count,
                    "emails": e_count
                })

        elif period == "quarterly":
            # Show last 4 quarters (1 year)
            for i in range(4):
                q_start = (today - timedelta(days=365 - (90*i)))
                q_end = (q_start + timedelta(days=90))
                
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at >= %s AND created_at < %s", (q_start, q_end))
                l_count = cur.fetchone()[0] or 0
                
                cur.execute("SELECT COUNT(*) FROM activity_log WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT') AND created_at >= %s AND created_at < %s", (q_start, q_end))
                e_count = cur.fetchone()[0] or 0
                
                velocity_data.append({
                    "day": f"Q{((q_start.month-1)//3)+1}",
                    "leads": l_count,
                    "emails": e_count
                })
            
        return velocity_data
    except Exception as e:
        logger.error(f"ADMIN VELOCITY ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Velocity Pipeline Failure: {str(e)}")
    finally:
        cur.close()
        conn.close()
@router.post("/admin/dispatch-report")
async def dispatch_admin_report(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Generates and dispatches a high-level summary report (stats only) to the Admin."""
    uid = normalize_user_id(user_id)
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # 1. Admin Verification
        cur.execute("SELECT email, role FROM users WHERE id = %s", (uid,))
        admin = cur.fetchone()
        if not admin or admin['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized")

        admin_email = admin['email'] or os.getenv("SENDER_EMAIL")

        # 2. Multi-Period Core Metrics Aggregation
        periods = [
            ("24 HOURS", "1 day"),
            ("7 DAYS", "7 days"),
            ("30 DAYS", "30 days")
        ]
        
        stats = []
        for label, interval in periods:
            # Leads Ingested
            cur.execute(f"SELECT COUNT(*) FROM leads_raw WHERE created_at > NOW() - INTERVAL '{interval}'")
            ingested = cur.fetchone()[0] or 0
            
            # Leads Sent (Email Sent)
            cur.execute(f"SELECT COUNT(*) FROM activity_log WHERE action IN ('SENT', 'EMAIL_SENT') AND created_at > NOW() - INTERVAL '{interval}'")
            sent = cur.fetchone()[0] or 0
            
            # Reverts (assuming manual tag or status change as 'REVERT' or 'REPLIED' in activity_log)
            cur.execute(f"SELECT COUNT(*) FROM activity_log WHERE action IN ('REVERT', 'REPLIED', 'STATUS_CHANGE') AND details ILIKE '%revert%' AND created_at > NOW() - INTERVAL '{interval}'")
            reverts = cur.fetchone()[0] or 0
            
            stats.append({
                "period": label,
                "ingested": ingested,
                "sent": sent,
                "reverts": reverts
            })

        # 3. Create Executive Summary Template
        html = f"""
        <html>
        <body style="font-family: 'Inter', Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 40px;">
            <div style="max-width: 800px; margin: 0 auto; background-color: #161b22; border-radius: 12px; border: 1px solid #30363d; padding: 40px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                <div style="text-align: center; margin-bottom: 40px;">
                    <h2 style="color: #58a6ff; font-weight: 900; letter-spacing: 3px; margin: 0; text-transform: uppercase; font-size: 13px;">Executive Summary</h2>
                    <h1 style="color: #ffffff; font-size: 32px; margin-top: 10px; font-weight: 900;">LeadStream <span style="font-style: italic; color: #58a6ff;">Intelligence</span></h1>
                </div>

                <div style="margin-bottom: 30px;">
                    <p style="font-size: 11px; font-weight: 800; color: #8b949e; text-transform: uppercase; letter-spacing: 2px;">System Performance Grid</p>
                </div>
        """
        
        for s in stats:
            html += f"""
                <div style="background: #0d1117; border-radius: 16px; border: 1px solid #30363d; padding: 25px; margin-bottom: 20px;">
                    <h3 style="color: #58a6ff; font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 20px; letter-spacing: 1px;">Period: {s['period']}</h3>
                    <div style="display: table; width: 100%;">
                        <div style="display: table-cell; width: 33%; text-align: left;">
                            <p style="font-size: 9px; color: #8b949e; text-transform: uppercase; font-weight: 900; margin-bottom: 5px;">Leads Ingested</p>
                            <p style="font-size: 22px; color: #ffffff; font-weight: 900; margin: 0;">{s['ingested']}</p>
                        </div>
                        <div style="display: table-cell; width: 33%; text-align: center; border-left: 1px solid #30363d;">
                            <p style="font-size: 9px; color: #8b949e; text-transform: uppercase; font-weight: 900; margin-bottom: 5px;">Leads Sent</p>
                            <p style="font-size: 22px; color: #58a6ff; font-weight: 900; margin: 0;">{s['sent']}</p>
                        </div>
                        <div style="display: table-cell; width: 33%; text-align: center; border-left: 1px solid #30363d;">
                            <p style="font-size: 9px; color: #8b949e; text-transform: uppercase; font-weight: 900; margin-bottom: 5px;">Reverted (Replies)</p>
                            <p style="font-size: 22px; color: #3fb950; font-weight: 900; margin: 0;">{s['reverts']}</p>
                        </div>
                    </div>
                </div>
            """
            
        html += """
                <div style="margin-top: 40px; padding: 20px; text-align: center; color: #8b949e; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; border-top: 1px solid #30363d;">
                    DISPATCHED BY LeadStream AI SYSTEM • {gen_time}
                </div>
            </div>
        </body>
        </html>
        """.replace("{gen_time}", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # 4. SMTP DISPATCH
        msg = MIMEMultipart()
        msg['From'] = os.getenv("SENDER_EMAIL")
        msg['To'] = admin_email
        msg['Subject'] = f"📊 Performance Summary | {datetime.now().strftime('%Y-%m-%d')}"
        msg.attach(MIMEText(html, 'html'))
        
        try:
            with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as server:
                server.starttls()
                server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
                server.send_message(msg)
            return {"success": True, "message": f"Summary dispatched to {admin_email}"}
        except Exception as e:
            logger.error(f"SUMMARY DISPATCH SMTP ERROR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Email Dispatch Failed: {str(e)}")

    finally:
        cur.close()
        conn.close()
