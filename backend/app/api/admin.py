from fastapi import APIRouter, HTTPException, Header, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import io
import csv
from app.database import get_db_connection
import psycopg2
import psycopg2.extras
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def normalize_user_id(user_id: Optional[str]) -> str:
    if not user_id or user_id.strip() == "" or user_id.lower() == "admin":
        return "1"
    return user_id

@router.get("/admin/stats")
async def get_admin_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
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
        return {"total_leads": total_leads, "active_users": active_users, "active_campaigns": active_campaigns, "sent_total": sent_total}
    finally:
        cur.close()
        conn.close()

@router.get("/admin/velocity")
async def get_admin_velocity(
    period: str = Query("daily", pattern="^(daily|weekly|monthly|quarterly)$"),
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()
        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized")
        today = datetime.now()
        velocity_data = []
        if period == "daily":
            cur.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM leads_raw WHERE created_at > CURRENT_DATE - INTERVAL '6 days'
                GROUP BY 1 ORDER BY 1
            """)
            leads_rows = {row['date']: row['count'] for row in cur.fetchall()}
            cur.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM activity_log WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT', 'EMAIL_SENT')
                AND created_at > CURRENT_DATE - INTERVAL '6 days'
                GROUP BY 1 ORDER BY 1
            """)
            activity_rows = {row['date']: row['count'] for row in cur.fetchall()}
            for i in range(7):
                d = (today - timedelta(days=6-i)).date()
                velocity_data.append({"day": d.strftime("%a"), "leads": leads_rows.get(d, 0), "emails": activity_rows.get(d, 0)})
        elif period == "weekly":
            for i in range(8):
                start_date = today - timedelta(weeks=8-i)
                end_date = today - timedelta(weeks=7-i)
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at >= %s AND created_at < %s", (start_date, end_date))
                l_count = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM activity_log WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT') AND created_at >= %s AND created_at < %s", (start_date, end_date))
                e_count = cur.fetchone()[0] or 0
                velocity_data.append({"day": f"Wk {i+1}", "leads": l_count, "emails": e_count})
        elif period == "monthly":
            for i in range(4):
                month_start = (today.replace(day=1) - timedelta(days=120 - (30*i))).replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1)
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at >= %s AND created_at < %s", (month_start, month_end))
                l_count = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM activity_log WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT') AND created_at >= %s AND created_at < %s", (month_start, month_end))
                e_count = cur.fetchone()[0] or 0
                velocity_data.append({"day": month_start.strftime("%b"), "leads": l_count, "emails": e_count})
        elif period == "quarterly":
            for i in range(4):
                q_start = (today - timedelta(days=365 - (90*i)))
                q_end = (q_start + timedelta(days=90))
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at >= %s AND created_at < %s", (q_start, q_end))
                l_count = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM activity_log WHERE action IN ('BULK_DRAFT_GENERATE', 'SENT') AND created_at >= %s AND created_at < %s", (q_start, q_end))
                e_count = cur.fetchone()[0] or 0
                velocity_data.append({"day": f"Q{((q_start.month-1)//3)+1}", "leads": l_count, "emails": e_count})
        return velocity_data
    except Exception as e:
        logger.error(f"ADMIN VELOCITY ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Velocity Pipeline Failure: {str(e)}")
    finally:
        cur.close()
        conn.close()


@router.post("/admin/dispatch-report")
async def dispatch_admin_report(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Full MIS Report with CSS bar charts and per-user summaries."""
    uid = normalize_user_id(user_id)
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute("SELECT email, role FROM users WHERE id = %s", (uid,))
        admin = cur.fetchone()
        if not admin or admin['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized")

        admin_email = admin['email'] or "harsh.b@qvscl.com"
        gen_time = datetime.now().strftime('%d %b %Y, %H:%M IST')

        # ─── SYSTEM KPIs ────────────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM leads_raw")
        total_leads = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL")
        total_drafted = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status='SENT'")
        total_sent = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status IN ('PENDING_APPROVAL','pending')")
        total_pending = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE validation_status='VALID'")
        total_valid = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at > NOW() - INTERVAL '24 hours'")
        leads_24h = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE created_at > NOW() - INTERVAL '7 days'")
        leads_7d = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(DISTINCT email) FROM unsubscribe_list")
        total_unsubs = cur.fetchone()[0] or 0

        # ─── PER-USER DATA ───────────────────────────────────────────────────
        cur.execute("""
            SELECT u.username, u.full_name,
                COUNT(l.id) AS total_leads,
                COUNT(CASE WHEN l.email_draft IS NOT NULL THEN 1 END) AS drafted,
                COUNT(CASE WHEN l.email_status='SENT' THEN 1 END) AS sent,
                COUNT(CASE WHEN l.email_status IN ('PENDING_APPROVAL','pending') THEN 1 END) AS pending,
                COUNT(CASE WHEN l.validation_status='VALID' THEN 1 END) AS valid,
                COUNT(CASE WHEN l.created_at > NOW() - INTERVAL '24 hours' THEN 1 END) AS added_today,
                COUNT(CASE WHEN l.source='bulk' THEN 1 END) AS bulk_leads,
                COUNT(CASE WHEN l.source='csv_import' THEN 1 END) AS csv_leads,
                COUNT(CASE WHEN l.source='direct' THEN 1 END) AS direct_leads,
                STRING_AGG(DISTINCT l.persona, ', ' ORDER BY l.persona) FILTER (WHERE l.persona IS NOT NULL) AS personas_used
            FROM users u
            LEFT JOIN leads_raw l ON l.user_id = u.id
            WHERE u.username != 'admin' AND u.is_active = TRUE
            GROUP BY u.id, u.username, u.full_name
            ORDER BY total_leads DESC
        """)
        user_rows = cur.fetchall()

        # ─── PIPELINE DISTRIBUTION ───────────────────────────────────────────
        cur.execute("SELECT persona, COUNT(*) as cnt FROM leads_raw WHERE persona IS NOT NULL GROUP BY persona ORDER BY cnt DESC")
        persona_rows = cur.fetchall()
        cur.execute("SELECT source, COUNT(*) as cnt FROM leads_raw WHERE source IS NOT NULL GROUP BY source ORDER BY cnt DESC")
        source_rows = cur.fetchall()
        cur.execute("SELECT validation_status, COUNT(*) as cnt FROM leads_raw WHERE validation_status IS NOT NULL GROUP BY validation_status ORDER BY cnt DESC")
        val_rows = cur.fetchall()
        cur.execute("SELECT company_name, COUNT(*) as cnt FROM leads_raw WHERE company_name IS NOT NULL AND company_name != '' GROUP BY company_name ORDER BY cnt DESC LIMIT 8")
        top_companies = cur.fetchall()

        # ─── 7-DAY TREND ─────────────────────────────────────────────────────
        cur.execute("""
            SELECT DATE(created_at) as d, COUNT(*) as cnt
            FROM leads_raw WHERE created_at > CURRENT_DATE - INTERVAL '6 days'
            GROUP BY 1 ORDER BY 1
        """)
        trend_rows = {row['d']: row['cnt'] for row in cur.fetchall()}
        trend_days = []
        for i in range(7):
            d = (datetime.now() - timedelta(days=6-i)).date()
            trend_days.append({"label": d.strftime("%a"), "cnt": trend_rows.get(d, 0)})
        trend_max = max((t['cnt'] for t in trend_days), default=1) or 1

        # ─── HTML HELPERS ─────────────────────────────────────────────────────
        def section(title, color="#58a6ff", emoji=""):
            return f"""
            <div style="margin:32px 0 16px;padding-bottom:10px;border-bottom:2px solid {color}30;">
              <span style="font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:3px;color:{color};">{emoji} {title}</span>
            </div>"""

        def stat_box(label, value, color="#58a6ff", sub=""):
            return f"""
            <td style="padding:6px;text-align:center;width:25%;">
              <div style="background:#0d1117;border:1px solid #30363d;border-top:3px solid {color};border-radius:10px;padding:18px 10px;">
                <div style="font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:1.5px;font-weight:800;margin-bottom:8px;">{label}</div>
                <div style="font-size:30px;font-weight:900;color:{color};line-height:1;">{value}</div>
                {f'<div style="font-size:9px;color:#8b949e;margin-top:6px;">{sub}</div>' if sub else ''}
              </div>
            </td>"""

        def bar_chart_row(label, value, max_val, color="#58a6ff", suffix=""):
            pct = max(2, round(value / max_val * 100)) if max_val > 0 else 2
            return f"""
            <tr>
              <td style="padding:7px 12px 7px 0;font-size:11px;color:#c9d1d9;white-space:nowrap;width:130px;">{label}</td>
              <td style="padding:7px 0;width:100%;">
                <div style="background:#21262d;border-radius:4px;height:20px;width:100%;position:relative;">
                  <div style="background:{color};border-radius:4px;height:20px;width:{pct}%;"></div>
                </div>
              </td>
              <td style="padding:7px 0 7px 12px;font-size:12px;font-weight:900;color:{color};white-space:nowrap;text-align:right;">{value}{suffix}</td>
            </tr>"""

        def trend_bar(label, value, max_val, color="#58a6ff"):
            h = max(4, round(value / max_val * 80)) if max_val > 0 else 4
            return f"""
            <td style="text-align:center;vertical-align:bottom;padding:0 4px;width:40px;">
              <div style="background:{color};border-radius:4px 4px 0 0;height:{h}px;width:28px;margin:0 auto;"></div>
              <div style="font-size:10px;color:#c9d1d9;font-weight:700;margin-top:4px;">{value}</div>
              <div style="font-size:9px;color:#8b949e;margin-top:2px;">{label}</div>
            </td>"""

        def user_summary(u):
            name = u['full_name'] or u['username']
            total = u['total_leads'] or 0
            drafted = u['drafted'] or 0
            sent = u['sent'] or 0
            pending = u['pending'] or 0
            today_added = u['added_today'] or 0
            bulk = u['bulk_leads'] or 0
            csv = u['csv_leads'] or 0
            direct = u['direct_leads'] or 0
            personas = u['personas_used'] or 'N/A'
            conv_rate = round(drafted / total * 100) if total > 0 else 0

            # Determine primary channel
            channel = "RocketReach bulk extraction" if bulk >= csv and bulk >= direct else \
                      "CSV/spreadsheet import" if csv >= direct else "direct lead form"

            # Determine status
            if today_added > 0:
                status_line = f"Active today — added {today_added} new lead{'s' if today_added > 1 else ''} to the pipeline."
            elif total > 0:
                status_line = f"No new leads today but has an existing pipeline of {total} leads."
            else:
                status_line = "No lead activity recorded yet."

            # Draft efficiency
            if conv_rate >= 60:
                draft_line = f"Strong draft conversion at {conv_rate}% — {drafted} of {total} leads have AI-generated emails ready."
            elif conv_rate > 0:
                draft_line = f"Draft conversion at {conv_rate}% — {drafted} emails drafted, {pending} pending approval."
            else:
                draft_line = "No email drafts generated yet. Leads need to be processed through the AI engine."

            # Source insight
            source_line = f"Primary ingest channel: {channel}. Targeting persona(s): {personas}."

            # Sent status
            sent_line = f"{sent} email{'s' if sent != 1 else ''} dispatched to prospects." if sent > 0 else "No outbound emails sent yet — drafts are awaiting approval."

            return f"""
            <div style="background:#0d1117;border:1px solid #30363d;border-left:3px solid #58a6ff;border-radius:10px;padding:20px 22px;margin-bottom:16px;">
              <div style="display:table;width:100%;margin-bottom:14px;">
                <div style="display:table-cell;vertical-align:middle;">
                  <div style="font-size:14px;font-weight:900;color:#ffffff;">{name}</div>
                  <div style="font-size:10px;color:#8b949e;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-top:2px;">{u['username']}</div>
                </div>
                <div style="display:table-cell;text-align:right;vertical-align:middle;">
                  <span style="background:#58a6ff15;border:1px solid #58a6ff30;border-radius:20px;padding:4px 14px;font-size:10px;font-weight:900;color:#58a6ff;">{total} Leads</span>
                </div>
              </div>
              <div style="font-size:12px;color:#c9d1d9;line-height:1.8;">
                <div style="margin-bottom:4px;">📌 {status_line}</div>
                <div style="margin-bottom:4px;">✉️ {draft_line}</div>
                <div style="margin-bottom:4px;">🔗 {source_line}</div>
                <div>🚀 {sent_line}</div>
              </div>
              <div style="display:table;width:100%;margin-top:16px;border-top:1px solid #21262d;padding-top:14px;">
                {''.join(f"""<div style="display:table-cell;text-align:center;">
                  <div style="font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:1px;font-weight:800;">{lbl}</div>
                  <div style="font-size:18px;font-weight:900;color:{clr};margin-top:4px;">{val}</div>
                </div>""" for lbl, val, clr in [
                    ('Total', total, '#c9d1d9'),
                    ('Drafted', drafted, '#a371f7'),
                    ('Pending', pending, '#e3b341'),
                    ('Sent', sent, '#58a6ff'),
                    ('Valid', u['valid'] or 0, '#3fb950'),
                ])}
              </div>
            </div>"""

        # ─── BUILD HTML ───────────────────────────────────────────────────────
        persona_max = max((p['cnt'] for p in persona_rows), default=1) or 1
        source_max  = max((s['cnt'] for s in source_rows), default=1) or 1
        val_max     = max((v['cnt'] for v in val_rows), default=1) or 1
        company_max = max((c['cnt'] for c in top_companies), default=1) or 1

        persona_colors = {"FOUNDER": "#58a6ff", "INVESTOR": "#3fb950", "PARTNER": "#a371f7", "OTHER": "#e3b341"}
        val_colors     = {"VALID": "#3fb950", "INVALID": "#f85149", "PENDING": "#e3b341"}
        source_colors  = {"bulk": "#58a6ff", "csv_import": "#3fb950", "direct": "#a371f7"}

        persona_bars  = "".join(bar_chart_row(p['persona'], p['cnt'], persona_max,
            persona_colors.get(p['persona'], "#8b949e")) for p in persona_rows)
        source_bars   = "".join(bar_chart_row(s['source'], s['cnt'], source_max,
            source_colors.get(s['source'], "#8b949e")) for s in source_rows)
        val_bars      = "".join(bar_chart_row(v['validation_status'], v['cnt'], val_max,
            val_colors.get(v['validation_status'], "#8b949e")) for v in val_rows)
        company_bars  = "".join(bar_chart_row(c['company_name'][:22], c['cnt'], company_max, "#f0883e") for c in top_companies)
        trend_bars_html = "".join(trend_bar(t['label'], t['cnt'], trend_max) for t in trend_days)
        user_cards    = "".join(user_summary(u) for u in user_rows)

        html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:'Inter',Arial,sans-serif;background:#090c12;color:#c9d1d9;margin:0;padding:32px;">
<div style="max-width:820px;margin:0 auto;background:#0d1117;border-radius:16px;border:1px solid #30363d;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,0.8);">

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg,#1a1f2e 0%,#0d1117 100%);padding:36px 44px;text-align:center;border-bottom:1px solid #30363d;">
    <div style="font-size:9px;font-weight:900;letter-spacing:5px;color:#58a6ff;text-transform:uppercase;margin-bottom:8px;">LeadStream AI · Management Information System</div>
    <h1 style="color:#fff;font-size:28px;font-weight:900;margin:0 0 8px;">Full MIS Report</h1>
    <div style="font-size:11px;color:#8b949e;font-weight:600;">{gen_time} &nbsp;·&nbsp; To: {admin_email}</div>
  </div>

  <div style="padding:36px 44px;">

    <!-- KPI GRID ROW 1 -->
    {section("System KPIs — All Time", "#58a6ff", "📊")}
    <table style="width:100%;border-collapse:separate;border-spacing:8px;">
      <tr>
        {stat_box("Total Leads", total_leads, "#58a6ff")}
        {stat_box("Valid Leads", total_valid, "#3fb950")}
        {stat_box("Refined Drafts", total_drafted, "#a371f7")}
        {stat_box("Pending Approval", total_pending, "#e3b341")}
      </tr>
      <tr>
        {stat_box("Emails Sent", total_sent, "#58a6ff")}
        {stat_box("Added (24h)", leads_24h, "#3fb950", "new today")}
        {stat_box("Added (7 Days)", leads_7d, "#f0883e", "this week")}
        {stat_box("Unsubscribes", total_unsubs, "#f85149", "opted out")}
      </tr>
    </table>

    <!-- 7-DAY TREND BAR CHART -->
    {section("Lead Ingestion — 7-Day Trend", "#3fb950", "📈")}
    <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px 20px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr style="vertical-align:bottom;height:100px;">
          {trend_bars_html}
        </tr>
      </table>
    </div>

    <!-- DUAL COLUMN CHARTS -->
    <table style="width:100%;border-collapse:separate;border-spacing:16px;margin-top:0;">
      <tr>
        <td style="vertical-align:top;width:50%;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;">
          <div style="font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:2px;color:#58a6ff;margin-bottom:14px;">🎯 Persona Distribution</div>
          <table style="width:100%;border-collapse:collapse;">{persona_bars}</table>
        </td>
        <td style="vertical-align:top;width:50%;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;">
          <div style="font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:2px;color:#e3b341;margin-bottom:14px;">✅ Validation Status</div>
          <table style="width:100%;border-collapse:collapse;">{val_bars}</table>
        </td>
      </tr>
      <tr>
        <td style="vertical-align:top;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;">
          <div style="font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:2px;color:#3fb950;margin-bottom:14px;">🔗 Lead Sources</div>
          <table style="width:100%;border-collapse:collapse;">{source_bars}</table>
        </td>
        <td style="vertical-align:top;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;">
          <div style="font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:2px;color:#f0883e;margin-bottom:14px;">🏢 Top Companies</div>
          <table style="width:100%;border-collapse:collapse;">{company_bars}</table>
        </td>
      </tr>
    </table>

    <!-- USER SUMMARIES -->
    {section("Agent Intelligence Summaries", "#a371f7", "👥")}
    {user_cards if user_cards else '<div style="color:#8b949e;font-size:12px;">No active agents found.</div>'}

  </div>

  <!-- FOOTER -->
  <div style="background:#090c12;border-top:1px solid #30363d;padding:20px 44px;text-align:center;font-size:9px;color:#8b949e;font-weight:700;text-transform:uppercase;letter-spacing:1px;">
    CONFIDENTIAL · LeadStream AI MIS System · {gen_time}
  </div>
</div>
</body>
</html>
"""

        msg = MIMEMultipart()
        msg['From'] = os.getenv("SENDER_EMAIL")
        msg['To'] = admin_email
        msg['Subject'] = f"📊 LeadStream MIS Report | {datetime.now().strftime('%d %b %Y, %H:%M')}"
        msg.attach(MIMEText(html, 'html'))

        try:
            with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as server:
                server.starttls()
                server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
                server.send_message(msg)
            return {"success": True, "message": f"Full MIS report dispatched to {admin_email}"}
        except Exception as e:
            logger.error(f"MIS DISPATCH SMTP ERROR: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Email Dispatch Failed: {str(e)}")

    finally:
        cur.close()
        conn.close()

@router.get("/admin/users-stats")
def get_users_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()
        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized")

        cur.execute("""
            SELECT 
                u.id, 
                u.username, 
                u.full_name, 
                u.email,
                u.role,
                (SELECT COUNT(*) FROM leads_raw l WHERE l.user_id::integer = u.id OR (u.role = 'ADMIN' AND l.user_id IS NULL)) as total_leads,
                (SELECT COUNT(*) FROM search_history sh WHERE sh.user_id::integer = u.id) as total_searches,
                (SELECT COALESCE(SUM(leads_ingested), 0) FROM search_history sh WHERE sh.user_id::integer = u.id) as captured_leads
            FROM users u
            WHERE u.is_active = TRUE
            ORDER BY total_leads DESC
        """)
        users = [dict(r) for r in cur.fetchall()]
        return users
    finally:
        cur.close()
        conn.close()

@router.get("/admin/audit-logs")
def get_audit_logs(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    target_user_id: Optional[int] = Query(None),
    action_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200)
):
    """Granular activity log with user and lead metadata."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()
        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Admin access required")

        where_clauses = []
        params = []

        if target_user_id:
            where_clauses.append("al.user_id = %s")
            params.append(target_user_id)
        
        if action_type:
            where_clauses.append("al.action = %s")
            params.append(action_type)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        offset = (page - 1) * limit

        # Fetch Logs
        query = f"""
            SELECT 
                al.*, 
                u.full_name as actor_name, 
                u.username as actor_username,
                l.first_name || ' ' || l.last_name as lead_name,
                l.email as lead_email,
                l.company_name as lead_company
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            LEFT JOIN leads_raw l ON al.lead_id = l.id
            {where_sql}
            ORDER BY al.created_at DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(query, params + [limit, offset])
        logs = [dict(r) for r in cur.fetchall()]

        # Total Count
        cur.execute(f"SELECT COUNT(*) FROM activity_log al {where_sql}", params)
        total = cur.fetchone()[0]

        # Serialization fix for datetime
        for log in logs:
            if log.get("created_at"):
                log["created_at"] = log["created_at"].isoformat()

        return {
            "logs": logs,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    finally:
        cur.close()
        conn.close()

@router.get("/admin/audit-logs/export")
def export_audit_logs(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    target_user_id: Optional[int] = Query(None)
):
    """Generates a CSV export of the activity audit trail."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()
        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Admin access required")

        where_sql = " WHERE al.user_id = %s" if target_user_id else ""
        params = [target_user_id] if target_user_id else []

        query = f"""
            SELECT 
                al.created_at, 
                u.full_name as actor,
                al.action, 
                al.details,
                l.first_name || ' ' || l.last_name as target_lead,
                l.email as lead_email
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            LEFT JOIN leads_raw l ON al.lead_id = l.id
            {where_sql}
            ORDER BY al.created_at DESC
            LIMIT 5000
        """
        cur.execute(query, params)
        rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "Actor", "Action", "Details", "Target Lead", "Email"])
        
        for r in rows:
            writer.writerow([
                r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r['created_at'] else '',
                r['actor'] or 'System',
                r['action'],
                r['details'] or '',
                r['target_lead'] or '',
                r['lead_email'] or ''
            ])

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leadstream_audit_log.csv"}
        )
    finally:
        cur.close()
        conn.close()
