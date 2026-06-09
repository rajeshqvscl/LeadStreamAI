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
    status: str = Query(None),
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    rng = _period_clause(period)
    dte = _date_clause(date_from, date_to)

    params = []
    where_parts = []
    resolved_id = None
    resolved_name = None
    if user_id and user_id != 'all':
        uid_val = user_id.strip()
        if uid_val.isdigit():
            cur.execute("SELECT id, full_name, username FROM users WHERE id = %s LIMIT 1", (int(uid_val),))
        else:
            cur.execute("SELECT id, full_name, username FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1", (uid_val, uid_val))
        row = cur.fetchone()
        if row:
            resolved_id = row['id']
            resolved_name = row['full_name'] or row['username']
        if resolved_id is not None:
            where_parts.append("user_id = %s")
            params.append(resolved_id)
        else:
            where_parts.append("1=0")
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
    if user_id and user_id != 'all' and resolved_id is not None:
        cur.execute("SELECT COUNT(*) as count FROM company_registry WHERE user_id = %s", (resolved_id,))
    else:
        cur.execute("SELECT COUNT(*) as count FROM company_registry WHERE 1=1")
    registry_count = cur.fetchone()['count'] or 0

    # Today sent (from activity_log, IST timezone)
    ist_today = "(NOW() AT TIME ZONE 'Asia/Kolkata')::date"
    ist_date = "(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date"
    if user_id and user_id != 'all' and resolved_id:
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE performed_by = %s AND action = 'EMAIL_SENT' AND {ist_date} = {ist_today}", (resolved_name or resolved_id,))
        today_sent = cur.fetchone()['count'] or 0
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE user_id = %s AND action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED') AND {ist_date} = {ist_today}", (resolved_id,))
        today_followups = cur.fetchone()['count'] or 0
    else:
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action = 'EMAIL_SENT' AND {ist_date} = {ist_today}")
        today_sent = cur.fetchone()['count'] or 0
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED') AND {ist_date} = {ist_today}")
        today_followups = cur.fetchone()['count'] or 0

    daily_limit = 2000

    # Period-based sent/followups (from activity_log with date filter)
    if date_from or date_to:
        al_date_parts = []
        al_date_params = []
        if user_id and user_id != 'all' and resolved_name:
            al_date_parts.append("performed_by = %s")
            al_date_params.append(resolved_name)
        al_date_parts.append("1=1")
        al_date_base = " AND ".join(al_date_parts)
        al_date_filter = ""
        if date_from:
            al_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'"
            al_date_params.append(date_from)
        if date_to:
            al_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'"
            al_date_params.append(date_to)
        al_params = tuple(al_date_params)
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action = 'EMAIL_SENT' AND {al_date_base} {al_date_filter}", al_params)
        period_email_sent = cur.fetchone()['count'] or 0
        # Follow-ups: use user_id column for per-user filter
        fup_date_parts = []
        fup_date_params = []
        if user_id and user_id != 'all' and resolved_id:
            fup_date_parts.append("user_id = %s")
            fup_date_params.append(resolved_id)
        fup_date_parts.append("1=1")
        fup_date_base = " AND ".join(fup_date_parts)
        fup_date_filter = ""
        if date_from:
            fup_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'"
            fup_date_params.append(date_from)
        if date_to:
            fup_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'"
            fup_date_params.append(date_to)
        fup_params = tuple(fup_date_params)
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED') AND {fup_date_base} {fup_date_filter}", fup_params)
        period_followups = cur.fetchone()['count'] or 0
    else:
        period_email_sent = 0
        period_followups = 0

    # Total follow-ups (all time)
    if user_id and user_id != 'all' and resolved_id:
        cur.execute("SELECT COUNT(*) as count FROM activity_log WHERE user_id = %s AND action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')", (resolved_id,))
    else:
        cur.execute("SELECT COUNT(*) as count FROM activity_log WHERE action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')")
    total_followups = cur.fetchone()['count'] or 0

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

    # Optional status filter (e.g. status=BOUNCED)
    if status:
        status_val = status.strip().upper()
        report_where.append("l.email_status = %s")
        report_params.append(status_val)

    # Detect Palak for 2-followup display
    _palak_user = False
    if resolved_id is not None and row:
        _un = str(row.get('username') or '').lower()
        _fn = str(row.get('full_name') or '').lower()
        if 'palak' in _un or 'palak' in _fn:
            _palak_user = True

    if user_id and user_id != 'all':
        if resolved_id is not None:
            report_where.append("l.user_id = %s")
            report_params.append(resolved_id)
        else:
            report_where.append("1=0")
    report_where.append("1=1")
    report_base = " AND ".join(report_where)
    report_filter = f"WHERE {report_base} {rng_report} {dte_report}".strip()
    report_params_t = tuple(report_params)
    if date_from:
        report_params_t = report_params_t + (date_from,)
    if date_to:
        report_params_t = report_params_t + (date_to,)

    cur.execute(f"""
        SELECT l.first_name, l.last_name, l.email, l.company_name, l.family_office_name,
               COALESCE(l.sector, 'Other') as sector,
               COALESCE(l.lead_type, 'CLIENT') as lead_type,
               l.email_status, l.followup_status, l.followup_stage,
               l.is_responded, l.is_unsubscribed, l.reply_intent, l.check_size,
               l.updated_at, l.first_outreach_subject,
               (SELECT al.details FROM activity_log al WHERE al.lead_id = l.id AND al.action = 'BOUNCED' ORDER BY al.created_at DESC LIMIT 1) as bounce_reason
        FROM leads_raw l
        {report_filter}
        ORDER BY l.updated_at DESC
    """, report_params_t)
    report_rows = cur.fetchall()

    report = []
    generic_domains = {"gmail", "yahoo", "hotmail", "outlook", "protonmail", "icloud", "qvscl", "me", "live", "microsoft", "samsung", "sea", "example"}
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
        _ms = 2 if _palak_user else 3
        if fs == 'ACTIVE':
            followup_display = f"Active ({stage}/{_ms})"
        elif fs == 'COMPLETED' or stage >= _ms:
            followup_display = f"Completed ({stage}/{_ms})"
        elif stage > 0:
            followup_display = f"Stage {stage}/{_ms}"
        else:
            followup_display = 'Not started'

        updated = r['updated_at']
        if updated:
            updated = updated.isoformat() if hasattr(updated, 'isoformat') else str(updated)

        # Company name: use family_office_name, then email domain, then Individual
        company_name = r['company_name'] or ''
        if not company_name or company_name.lower() == 'independent':
            company_name = r.get('family_office_name') or ''
        if not company_name:
            email = r['email'] or ''
            if '@' in email:
                domain_part = email.split('@')[-1].split('.')[0].lower()
                if domain_part not in generic_domains:
                    company_name = domain_part.capitalize()
        if not company_name:
            company_name = 'Individual'

        # Sector: always infer from subject first, fallback to DB sector or lead_type
        subject = r.get('first_outreach_subject') or ''
        s_lower = subject.lower()
        if 'climate' in s_lower or 'agri' in s_lower:
            sector = 'Climate AI'
        elif 'hiring' in s_lower or 'recruitment' in s_lower or 'talent' in s_lower:
            sector = 'AI Hiring'
        elif 'health' in s_lower or 'diagnostics' in s_lower or 'pharma' in s_lower:
            sector = 'HealthTech'
        elif 'warehouse' in s_lower or 'logistics' in s_lower or 'fulfilment' in s_lower:
            sector = 'Logistics'
        elif 'fund' in s_lower or 'invest' in s_lower or 'capital' in s_lower or 'venture' in s_lower:
            sector = 'Investment'
        elif 'ai' in s_lower or 'software' in s_lower or 'saas' in s_lower or 'tech' in s_lower:
            sector = 'AI / Tech'
        else:
            sector = r['sector'] or 'Other'
            if sector == 'Other':
                sector = r.get('lead_type') or 'CLIENT'
                sector = sector.replace('_', ' ').title()

        report.append({
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "email": r['email'] or '',
            "company": company_name,
            "sector": sector,
            "action": action,
            "followup": followup_display,
            "date": updated,
            "bounce_reason": r.get('bounce_reason') or '',
            "first_outreach_subject": r.get('first_outreach_subject') or '',
            "check_size": r.get('check_size') or '',
        })

    cur.close()
    conn.close()

    return {
        "total_registry": registry_count,
        "today_sent": today_sent,
        "today_followups": today_followups,
        "total_followups": total_followups,
        "period_email_sent": period_email_sent,
        "period_followups": period_followups,
        "daily_limit": daily_limit,
        "drafts_generated": drafts_generated,
        "reverted": reverted,
        "total_leads": leads_count,
        "sent": period_email_sent if date_from or date_to else sent,
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
