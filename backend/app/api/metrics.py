from fastapi import APIRouter, Header, Query
from typing import Optional
from app.database import get_db_connection
import psycopg2.extras
from datetime import datetime, timezone

router = APIRouter(tags=["Metrics"])

def _period_clause(val):
    v = (val or '').strip().lower()
    if v == 'daily':
        return "AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < ((NOW() AT TIME ZONE 'Asia/Kolkata')::date + INTERVAL '1 day')"
    elif v == 'weekly':
        return "AND updated_at >= NOW() - INTERVAL '7 days'"
    elif v == 'monthly':
        return "AND updated_at >= NOW() - INTERVAL '30 days'"
    return ""

def _period_clause_report(val):
    v = (val or '').strip().lower()
    if v == 'daily':
        return "AND l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date AND l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < ((NOW() AT TIME ZONE 'Asia/Kolkata')::date + INTERVAL '1 day')"
    elif v == 'weekly':
        return "AND l.updated_at >= NOW() - INTERVAL '7 days'"
    elif v == 'monthly':
        return "AND l.updated_at >= NOW() - INTERVAL '30 days'"
    return ""

def _date_clause(date_from, date_to):
    clauses = []
    if date_from:
        clauses.append(f"AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'")
    if date_to:
        clauses.append(f"AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'")
    return " ".join(clauses)

def _date_clause_report(date_from, date_to):
    clauses = []
    if date_from:
        clauses.append(f"AND l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'")
    if date_to:
        clauses.append(f"AND l.updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'")
    return " ".join(clauses)

@router.get("/metrics")
def get_metrics(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    period: str = Query('all'),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    rng = _period_clause(period)
    dte = _date_clause(date_from, date_to)

    params = []
    where_parts = []
    if user_id and user_id != 'all':
        where_parts.append("user_id = %s")
        params.append(user_id)
    where_parts.append("1=1")
    where_base = " AND ".join(where_parts)
    where_clause = f"WHERE {where_base} {rng} {dte}".strip()

    # Build full params list: user_id first, then date_from, date_to
    full_params = tuple(params)
    if date_from:
        full_params = full_params + (date_from,)
    if date_to:
        full_params = full_params + (date_to,)

    # Drafts = leads with PENDING_APPROVAL status (in review queue)
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND email_status = 'PENDING_APPROVAL'", full_params)
    drafts_generated = cur.fetchone()['count'] or 0

    # Reverted = leads that replied
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND (is_responded = TRUE OR email_status IN ('REPLIED', 'INTERESTED', 'MEETING SCHEDULED'))", full_params)
    reverted = cur.fetchone()['count'] or 0

    # Total leads (with range)
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause}", full_params)
    leads_count = cur.fetchone()['count'] or 0

    # Registry (without range)
    if user_id and user_id != 'all':
        cur.execute("SELECT COUNT(*) as count FROM company_registry WHERE user_id = %s", (user_id,))
    else:
        cur.execute("SELECT COUNT(*) as count FROM company_registry WHERE 1=1")
    registry_count = cur.fetchone()['count'] or 0

    # Today sent (from activity_log, IST timezone)
    ist_today = "(NOW() AT TIME ZONE 'Asia/Kolkata')::date"
    ist_date = "(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date"
    if user_id and user_id != 'all':
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE user_id = %s AND action = 'EMAIL_SENT' AND {ist_date} = {ist_today}", (user_id,))
        today_sent = cur.fetchone()['count'] or 0
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE user_id = %s AND action IN ('FOLLOWUP_SENT', 'AUTO_FOLLOWUP_SENT') AND {ist_date} = {ist_today}", (user_id,))
        today_followups = cur.fetchone()['count'] or 0
    else:
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action = 'EMAIL_SENT' AND {ist_date} = {ist_today}")
        today_sent = cur.fetchone()['count'] or 0
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action IN ('FOLLOWUP_SENT', 'AUTO_FOLLOWUP_SENT') AND {ist_date} = {ist_today}")
        today_followups = cur.fetchone()['count'] or 0

    daily_limit = 2000

    # Bounces
    cur.execute(f"SELECT COUNT(*) FROM leads_raw {where_clause} AND email_status = 'BOUNCED'", full_params)
    bounce_count = cur.fetchone()['count'] or 0

    # Sent
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND email_status IN ('SENT', 'OPENED', 'REPLIED', 'Meeting Scheduled', 'Contacted', 'Interested', 'CLICKED')", full_params)
    sent = cur.fetchone()['count'] or 0

    delivered = max(sent - bounce_count, 0)
    unique_opens = reverted
    unique_engaged = reverted
    unique_clicks = 0

    open_rate = (unique_opens / delivered * 100) if delivered > 0 else 0.0
    bounce_rate = (bounce_count / sent * 100) if sent > 0 else 0.0
    engagement_rate = (unique_engaged / delivered * 100) if delivered > 0 else 0.0
    conversion_rate = (unique_engaged / leads_count * 100) if leads_count > 0 else 0.0

    # Persona breakdown
    cur.execute(f"SELECT COALESCE(lead_type, 'OTHER') as persona, COUNT(*) as count FROM leads_raw {where_clause} GROUP BY COALESCE(lead_type, 'OTHER')", full_params)
    persona_rows = cur.fetchall()
    persona_breakdown = { r['persona'].upper(): r['count'] for r in persona_rows }

    # Sector breakdown
    cur.execute(f"SELECT COALESCE(sector, 'Other') as industry, COUNT(*) as count FROM leads_raw {where_clause} GROUP BY COALESCE(sector, 'Other') ORDER BY count DESC LIMIT 10", full_params)
    industry_rows = cur.fetchall()
    industry_breakdown = { r['industry']: r['count'] for r in industry_rows }

    # Country breakdown
    cur.execute(f'''
        SELECT COALESCE(country, raw_payload->>'country', 'Unknown') as country, COUNT(*) as count 
        FROM leads_raw 
        {where_clause}
        AND COALESCE(country, raw_payload->>'country') IS NOT NULL
        GROUP BY 1
        ORDER BY count DESC 
        LIMIT 8
    ''', full_params)
    country_rows = cur.fetchall()
    country_breakdown = { r['country']: r['count'] for r in country_rows }

    # Per-lead report data
    rng_report = _period_clause_report(period)
    dte_report = _date_clause_report(date_from, date_to)
    report_params = []
    report_where = []
    if user_id and user_id != 'all':
        report_where.append("l.user_id = %s")
        report_params.append(user_id)
    report_where.append("1=1")
    report_base = " AND ".join(report_where)
    report_filter = f"WHERE {report_base} {rng_report} {dte_report}".strip()
    report_params_t = tuple(report_params)
    if date_from:
        report_params_t = report_params_t + (date_from,)
    if date_to:
        report_params_t = report_params_t + (date_to,)

    cur.execute(f"""
        SELECT l.first_name, l.last_name, l.email, l.company_name,
               COALESCE(l.sector, 'Other') as sector,
               l.email_status, l.followup_status, l.followup_stage,
               l.is_responded, l.is_unsubscribed, l.reply_intent,
               l.updated_at
        FROM leads_raw l
        {report_filter}
        ORDER BY l.updated_at DESC
    """, report_params_t)
    report_rows = cur.fetchall()

    report = []
    for r in report_rows:
        status = (r['email_status'] or '').upper()
        reply_intent = (r['reply_intent'] or '').upper()

        if r.get('is_unsubscribed') or reply_intent == 'NOT_INTERESTED':
            action = 'Rejected'
        elif status == 'BOUNCED':
            action = 'Bounced'
        elif status == 'CLICKED' or r.get('is_responded'):
            action = 'Clicked'
        elif status == 'OPENED':
            action = 'Opened'
        elif status in ('REPLIED', 'INTERESTED', 'MEETING SCHEDULED'):
            action = 'Replied'
        elif status in ('SENT', 'CONTACTED'):
            action = 'Sent'
        else:
            action = 'Pending'

        fs = (r['followup_status'] or '').upper()
        stage = r['followup_stage'] or 0
        if fs == 'ACTIVE':
            followup_display = f"Active ({stage}/3)"
        elif fs == 'COMPLETED' or stage >= 3:
            followup_display = f"Completed ({stage}/3)"
        elif stage > 0:
            followup_display = f"Stage {stage}/3"
        else:
            followup_display = 'Not started'

        updated = r['updated_at']
        if updated:
            updated = updated.isoformat() if hasattr(updated, 'isoformat') else str(updated)

        report.append({
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "email": r['email'] or '',
            "company": r['company_name'] or '',
            "sector": r['sector'] or 'Other',
            "action": action,
            "followup": followup_display,
            "date": updated,
        })

    cur.close()
    conn.close()

    return {
        "total_registry": registry_count,
        "today_sent": today_sent,
        "today_followups": today_followups,
        "daily_limit": daily_limit,
        "drafts_generated": drafts_generated,
        "reverted": reverted,
        "total_leads": leads_count,
        "sent": sent,
        "delivered": delivered,
        "unique_opens": unique_opens,
        "unique_clicks": unique_clicks,
        "unique_engaged": unique_engaged,
        "bounces": bounce_count,

        "open_rate": round(open_rate, 2),
        "bounce_rate": round(bounce_rate, 2),
        "engagement_rate": round(engagement_rate, 2),
        "conversion_rate": round(conversion_rate, 2),

        "persona_breakdown": persona_breakdown,
        "industry_breakdown": industry_breakdown,
        "country_breakdown": country_breakdown,
        "report": report,

        "timestamp": datetime.now(timezone.utc).isoformat()
    }
