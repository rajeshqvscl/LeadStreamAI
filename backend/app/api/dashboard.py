from fastapi import APIRouter, Header
from app.database import get_db_connection
import psycopg2.extras
from typing import Optional

router = APIRouter()

@router.get("/dashboard/stats")
def get_dashboard_stats(
    month: Optional[int] = None,
    year: Optional[int] = None,
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    is_admin = (str(user_id or '').lower() == 'admin')

    # Build date filter condition
    date_cond = ""
    date_params = []
    if month and year:
        date_cond = "AND EXTRACT(MONTH FROM created_at) = %s AND EXTRACT(YEAR FROM created_at) = %s"
        date_params = [month, year]
    elif month:
        date_cond = "AND EXTRACT(MONTH FROM created_at) = %s"
        date_params = [month]
    elif year:
        date_cond = "AND EXTRACT(YEAR FROM created_at) = %s"
        date_params = [year]
    # For tables with different timestamp column
    date_cond_unsub = date_cond.replace("created_at", "unsubscribed_at") if date_cond else ""

    # Resolve user_id to numeric DB id + full_name for activity_log queries
    # (activity_log stores performed_by=full_name or username, not user_id)
    resolved_id = None
    resolved_name = None
    if user_id and not is_admin and user_id.strip():
        uid_value = user_id.strip()
        if uid_value.isdigit():
            cur.execute("SELECT id, full_name, username FROM users WHERE id = %s LIMIT 1", (int(uid_value),))
        else:
            cur.execute("SELECT id, full_name, username FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1", (uid_value, uid_value))
        row = cur.fetchone()
        if row:
            resolved_id = row['id']
            resolved_name = row['full_name'] or row['username']

    if is_admin:
        user_cond = "1=1"
        user_params = []
        act_cond = "1=1"
        act_params = []
    elif resolved_id is not None:
        user_cond = "user_id = %s"
        user_params = [resolved_id]
        act_cond = "performed_by = %s"
        act_params = [resolved_name]
    else:
        user_cond = "user_id IS NULL"
        user_params = []
        act_cond = "1=1"
        act_params = []

    # Build date filter for leads_raw (has created_at column)
    lr_date = ""
    lr_date_params = []
    if date_cond:
        lr_date = date_cond
        lr_date_params = date_params
    # Build date filter for company_registry (has created_at column)
    cr_date = lr_date
    cr_date_params = lr_date_params

    # Single query for all counts
    company_count_sql = user_cond if is_admin or resolved_id is not None else "1=1"
    all_params = user_params + lr_date_params
    cur.execute(f"""
        SELECT
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date}) AS total_ingested,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND is_responded = TRUE) AS total_leads,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND validation_status = 'VALID') AS valid_leads,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND persona IS NOT NULL AND persona != '') AS classified,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND (email_status = 'PENDING_APPROVAL' OR email_status = 'pending')) AS pending,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND email_status = 'SENT') AS sent,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND email_draft IS NOT NULL) AS refined,
            (SELECT COUNT(*) FROM company_registry WHERE {company_count_sql} {cr_date}) AS total_companies,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND email_status = 'OPENED') AS unique_opens,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND email_status = 'CLICKED') AS unique_clicks,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND email_status = 'BOUNCED') AS total_bounces,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND email IS NOT NULL AND email != '') AS with_email,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {lr_date} AND linkedin_url IS NOT NULL AND linkedin_url != '') AS with_linkedin
    """, all_params * 13 if all_params else [])
    
    row = cur.fetchone()
    
    total_ingested = row['total_ingested'] or 0
    total_leads = row['total_leads'] or 0
    valid_leads = row['valid_leads'] or 0
    classified = row['classified'] or 0
    pending = row['pending'] or 0
    sent = row['sent'] or 0
    refined = row['refined'] or 0
    total_companies = row['total_companies'] or 0
    unique_opens = row['unique_opens'] or 0
    unique_clicks = row['unique_clicks'] or 0
    total_bounces = row['total_bounces'] or 0
    with_email = row['with_email'] or 0
    with_linkedin = row['with_linkedin'] or 0

    # Get unsubscribes count
    unsub_params = user_params + lr_date_params
    cur.execute(f"SELECT COUNT(*) as unsubs FROM unsubscribe_list WHERE email IN (SELECT email FROM leads_raw WHERE {user_cond} {lr_date})", unsub_params)
    total_unsubs = cur.fetchone()['unsubs'] or 0

    # Build date filter for activity_log (has created_at column)
    al_date = lr_date
    al_date_params = lr_date_params

    # Also check activity_log + campaign_events for opens/clicks (tracking pixel fallback)
    try:
        log_params = act_params + al_date_params if act_params else al_date_params
        log_params_2x = log_params + log_params if log_params else []
        cur.execute(f"""
            SELECT 
                (SELECT COUNT(DISTINCT lead_id) FROM activity_log WHERE action IN ('OPENED','EMAIL_OPENED') AND {act_cond} {al_date}) AS log_opens,
                (SELECT COUNT(DISTINCT lead_id) FROM activity_log WHERE action IN ('CLICKED','EMAIL_CLICKED') AND {act_cond} {al_date}) AS log_clicks
        """, log_params_2x if log_params_2x else [])
        log_row = cur.fetchone()
        log_opens = log_row['log_opens'] or 0
        log_clicks = log_row['log_clicks'] or 0
        unique_opens = max(unique_opens, log_opens)
        unique_clicks = max(unique_clicks, log_clicks)
    except:
        pass

    # Also check campaign_events table for additional tracking
    try:
        ce_date = lr_date.replace('created_at', 'ce.created_at') if lr_date else ""
        if is_admin:
            admin_ce_date = lr_date.replace('created_at', 'created_at') if lr_date else ""
            cur.execute(f"""
                SELECT 
                    (SELECT COUNT(DISTINCT recipient_id) FROM campaign_events WHERE event_type = 'OPEN' {admin_ce_date}) AS ce_opens,
                    (SELECT COUNT(DISTINCT recipient_id) FROM campaign_events WHERE event_type = 'CLICK' {admin_ce_date}) AS ce_clicks
            """, lr_date_params * 2 if lr_date_params else [])
        else:
            cur.execute(f"""
                SELECT 
                    (SELECT COUNT(DISTINCT ce.recipient_id) FROM campaign_events ce
                     JOIN recipients r ON ce.recipient_id = r.id
                     JOIN leads_raw l ON r.lead_id = l.id
                     WHERE ce.event_type = 'OPEN' AND {user_cond.replace('user_id', 'l.user_id')} {ce_date}) AS ce_opens,
                    (SELECT COUNT(DISTINCT ce.recipient_id) FROM campaign_events ce
                     JOIN recipients r ON ce.recipient_id = r.id
                     JOIN leads_raw l ON r.lead_id = l.id
                     WHERE ce.event_type = 'CLICK' AND {user_cond.replace('user_id', 'l.user_id')} {ce_date}) AS ce_clicks
            """, user_params * 2 if user_params else (lr_date_params * 2 if lr_date_params else []))
        ce_row = cur.fetchone()
        unique_opens = max(unique_opens, (ce_row['ce_opens'] or 0))
        unique_clicks = max(unique_clicks, (ce_row['ce_clicks'] or 0))
    except:
        pass

    # Rate Calculations (using lead enrichment as fallback for pulse when no emails are sent)
    if sent > 0:
        open_rate = float(f"{(unique_opens / sent * 100):.1f}")
        click_rate = float(f"{(unique_clicks / sent * 100):.1f}")
        bounce_rate = float(f"{(total_bounces / sent * 100):.1f}")
        unsub_rate = float(f"{(total_unsubs / sent * 100):.1f}")
        engagement_rate = float(f"{((unique_opens + unique_clicks) / sent * 100):.1f}")
    else:
        # Fallback metrics to show discovery/enrichment "Pulse" before sending
        engagement_rate = float(f"{(classified / total_leads * 100):.1f}") if total_leads > 0 else 0.0
        open_rate = float(f"{(with_email / total_leads * 100):.1f}") if total_leads > 0 else 0.0
        click_rate = float(f"{(with_linkedin / total_leads * 100):.1f}") if total_leads > 0 else 0.0
        
        unique_opens = with_email
        unique_clicks = with_linkedin
        
        bounce_rate = 0.0
        unsub_rate = float(f"{(total_unsubs / total_leads * 100):.1f}") if total_leads > 0 else 0.0

    cur.execute(f"SELECT persona, COUNT(*) as count FROM leads_raw WHERE {user_cond} {lr_date} AND persona IS NOT NULL GROUP BY persona", user_params + lr_date_params)

    persona_rows = cur.fetchall()
    persona_data = {}
    for r in persona_rows:
        if r['persona']:
            persona_data[r['persona']] = r['count']
        
    cur.execute(f"SELECT * FROM activity_log WHERE {act_cond} {al_date} ORDER BY created_at DESC LIMIT 7", act_params + al_date_params if act_params and al_date_params else (act_params if act_params else (al_date_params if al_date_params else [])))
    logs_rows = cur.fetchall()
    recent_logs = []
    for row in logs_rows:
        recent_logs.append(dict(row))

        
    # Count of emails sent today (using activity_log for accuracy, IST timezone)
    # Today counts — always today regardless of month filter
    ist_date = "(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date"
    today_str = "(NOW() AT TIME ZONE 'Asia/Kolkata')::date"
    cur.execute(f"""
        SELECT
            (SELECT COUNT(*) FROM activity_log WHERE action = 'EMAIL_SENT' AND {act_cond} AND {ist_date} = {today_str}) AS sent_today,
            (SELECT COUNT(*) FROM activity_log WHERE action IN ('FOLLOWUP_SENT','AUTO_FOLLOWUP_SENT') AND {act_cond} AND {ist_date} = {today_str}) AS fup_today
    """, act_params * 2 if act_params else [])
    today_row = cur.fetchone()
    sent_today = today_row['sent_today'] or 0
    fup_today = today_row['fup_today'] or 0

    # Total follow-ups count (with month/year filter if provided)
    fup_params = act_params + al_date_params if act_params and al_date_params else (act_params if act_params else (al_date_params if al_date_params else []))
    cur.execute(f"SELECT COUNT(*) as total FROM activity_log WHERE action IN ('FOLLOWUP_SENT','AUTO_FOLLOWUP_SENT') AND {act_cond} {al_date}", fup_params)
    total_followups = cur.fetchone()['total'] or 0

    # Pending meeting reminders count
    try:
        if is_admin:
            cur.execute("SELECT COUNT(*) as total FROM reminders WHERE status = 'PENDING'")
        elif resolved_id is not None:
            cur.execute("SELECT COUNT(*) as total FROM reminders WHERE status = 'PENDING' AND user_id = %s", (resolved_id,))
        else:
            rem_count = 0
        if not is_admin and resolved_id is None:
            meeting_reminders = 0
        else:
            meeting_reminders = cur.fetchone()['total'] or 0
    except:
        meeting_reminders = 0

    cur.close()
    conn.close()

    return {
        "total_ingested": total_ingested,
        "total_leads": total_leads,
        "valid_leads": valid_leads,
        "classified": classified,
        "pending": pending,
        "sent": sent,
        "refined": refined,
        "daily_sent_count": sent_today,
        "today_followups": fup_today,
        "total_followups": total_followups,
        "daily_limit": 2000,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "unique_opens": unique_opens,
        "unique_clicks": unique_clicks,
        "engagement_rate": engagement_rate,
        "bounce_rate": bounce_rate,
        "total_bounces": total_bounces,
        "total_unsubs": total_unsubs,
        "unsub_rate": unsub_rate,
        "recent_logs": recent_logs,
        "persona_data": persona_data if persona_data else { "FOUNDER": 0, "INVESTOR": 0, "PARTNER": 0 },
        "total_companies": total_companies,
        "filter_month": month,
        "filter_year": year,
        "pending_reminders": meeting_reminders
    }

@router.get("/dashboard/card-detail")
def get_card_detail(
    card_type: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    page: int = 1,
    per_page: int = 100,
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    is_admin = (str(user_id or '').lower() == 'admin')
    resolved_id = None
    if user_id and not is_admin and user_id.strip():
        uid_value = user_id.strip()
        if uid_value.isdigit():
            cur.execute("SELECT id, full_name, username FROM users WHERE id = %s LIMIT 1", (int(uid_value),))
        else:
            cur.execute("SELECT id, full_name, username FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1", (uid_value, uid_value))
        row = cur.fetchone()
        if row:
            resolved_id = row['id']

    if is_admin:
        user_cond = "1=1"
        user_params = []
        act_cond = "1=1"
        act_params = []
    elif resolved_id is not None:
        user_cond = "user_id = %s"
        user_params = [resolved_id]
        act_cond = "user_id = %s"
        act_params = [resolved_id]
    else:
        user_cond = "user_id IS NULL"
        user_params = []
        act_cond = "1=1"
        act_params = []

    # Month/year filter on created_at
    date_cond = ""
    date_params = []
    if month and year:
        date_cond = "AND EXTRACT(MONTH FROM created_at) = %s AND EXTRACT(YEAR FROM created_at) = %s"
        date_params = [month, year]
    elif month:
        date_cond = "AND EXTRACT(MONTH FROM created_at) = %s"
        date_params = [month]
    elif year:
        date_cond = "AND EXTRACT(YEAR FROM created_at) = %s"
        date_params = [year]

    offset = (page - 1) * per_page

    valid_types = ['pipeline', 'classified', 'pending', 'refined', 'unsubscribed', 'outbound',
                   'ingested', 'followups', 'open_rate_detail', 'click_rate_detail', 'bounce_detail', 'optouts_detail']
    if card_type not in valid_types:
        cur.close()
        conn.close()
        return {"error": f"Invalid card_type. Must be one of: {', '.join(valid_types)}"}

    if card_type == 'ingested':
        all_params = user_params + date_params
        count_sql = f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} {date_cond}"
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, created_at, source, validation_status
            FROM leads_raw WHERE {user_cond} {date_cond}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'followups':
        all_params = act_params + date_params
        count_sql = f"SELECT COUNT(*) FROM activity_log WHERE action IN ('FOLLOWUP_SENT','AUTO_FOLLOWUP_SENT') AND {act_cond} {date_cond.replace('created_at', 'created_at')}"
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT al.id, al.lead_id, al.action, al.details, al.created_at,
                   l.first_name, l.last_name, l.email, l.company_name, l.persona
            FROM activity_log al
            LEFT JOIN leads_raw l ON al.lead_id = l.id
            WHERE al.action IN ('FOLLOWUP_SENT','AUTO_FOLLOWUP_SENT') AND {act_cond.replace('user_id', 'al.user_id')} {date_cond.replace('created_at', 'al.created_at')}
            ORDER BY al.created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'open_rate_detail':
        open_cond = "(email_status = 'OPENED')"
        cur.execute(f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND {open_cond} {date_cond}", user_params + date_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, created_at, source
            FROM leads_raw WHERE {user_cond} AND {open_cond} {date_cond}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, user_params + date_params + [per_page, offset])

    elif card_type == 'click_rate_detail':
        click_cond = "(email_status = 'CLICKED')"
        cur.execute(f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND {click_cond} {date_cond}", user_params + date_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, created_at, source
            FROM leads_raw WHERE {user_cond} AND {click_cond} {date_cond}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, user_params + date_params + [per_page, offset])

    elif card_type == 'bounce_detail':
        bounce_cond = "(email_status = 'BOUNCED')"
        bounce_date = date_cond.replace('created_at', 'updated_at')
        cur.execute(f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND {bounce_cond} {bounce_date}", user_params + date_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, created_at, updated_at, source,
                   (SELECT al.details FROM activity_log al WHERE al.lead_id = leads_raw.id AND al.action = 'BOUNCED' ORDER BY al.created_at DESC LIMIT 1) as bounce_reason
            FROM leads_raw WHERE {user_cond} AND {bounce_cond} {bounce_date}
            ORDER BY updated_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, user_params + date_params + [per_page, offset])
        # Must fetch data BEFORE running any other query on same cursor
        bounce_rows = cur.fetchall()
        bounce_records = [dict(r) for r in bounce_rows]
        
        company_breakdown = []
        try:
            breakdown_sql = f"""
                SELECT company_name, COUNT(*) as count FROM leads_raw
                WHERE {user_cond} AND {bounce_cond} {bounce_date} AND company_name IS NOT NULL
                GROUP BY company_name ORDER BY count DESC LIMIT 10
            """
            cur.execute(breakdown_sql, user_params + date_params)
            company_breakdown = [dict(r) for r in cur.fetchall()]
        except:
            pass

    elif card_type == 'optouts_detail':
        all_params = user_params + date_params
        count_sql = f"""
            SELECT COUNT(*) FROM unsubscribe_list u
            JOIN leads_raw l ON u.email = l.email WHERE {user_cond} {date_cond.replace('created_at', 'u.unsubscribed_at')}
        """
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.company_name, l.persona,
                   u.reason, u.unsubscribed_at as created_at
            FROM unsubscribe_list u JOIN leads_raw l ON u.email = l.email
            WHERE {user_cond} {date_cond.replace('created_at', 'u.unsubscribed_at')}
            ORDER BY u.unsubscribed_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'unsubscribed':
        all_params = user_params + date_params
        count_sql = f"""
            SELECT COUNT(*) FROM unsubscribe_list u JOIN leads_raw l ON u.email = l.email
            WHERE {user_cond} {date_cond.replace('created_at', 'u.unsubscribed_at')}
        """
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.company_name, l.persona,
                   u.reason, u.source as unsub_source, u.unsubscribed_at as created_at
            FROM unsubscribe_list u JOIN leads_raw l ON u.email = l.email
            WHERE {user_cond} {date_cond.replace('created_at', 'u.unsubscribed_at')}
            ORDER BY u.unsubscribed_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'outbound':
        all_params = act_params + date_params
        count_sql = f"SELECT COUNT(*) FROM activity_log WHERE action = 'EMAIL_SENT' AND {act_cond} {date_cond.replace('created_at', 'created_at')}"
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT al.id, al.lead_id, al.action, al.details, al.created_at,
                   l.first_name, l.last_name, l.email, l.company_name
            FROM activity_log al LEFT JOIN leads_raw l ON al.lead_id = l.id
            WHERE al.action = 'EMAIL_SENT' AND {act_cond.replace('user_id', 'al.user_id')} {date_cond.replace('created_at', 'al.created_at')}
            ORDER BY al.created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'pipeline':
        all_params = user_params + date_params
        count_sql = f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND is_responded = TRUE {date_cond}"
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, created_at, source, is_unsubscribed
            FROM leads_raw WHERE {user_cond} AND is_responded = TRUE {date_cond}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'classified':
        all_params = user_params + date_params
        count_sql = f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND persona IS NOT NULL AND persona != '' {date_cond}"
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, email_draft IS NOT NULL as has_draft,
                   followup_stage, followup_status, created_at, source
            FROM leads_raw WHERE {user_cond} AND persona IS NOT NULL AND persona != '' {date_cond}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'pending':
        all_params = user_params + date_params
        count_sql = f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND (email_status = 'PENDING_APPROVAL' OR email_status = 'pending') {date_cond}"
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, LEFT(email_draft, 200) as draft_preview, created_at, source
            FROM leads_raw WHERE {user_cond} AND (email_status = 'PENDING_APPROVAL' OR email_status = 'pending') {date_cond}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    elif card_type == 'refined':
        all_params = user_params + date_params
        count_sql = f"SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND email_draft IS NOT NULL {date_cond}"
        cur.execute(count_sql, all_params)
        total = cur.fetchone()[0] or 0
        data_sql = f"""
            SELECT id, first_name, last_name, email, company_name, persona,
                   email_status, created_at, source,
                   LEFT(email_draft, 300) as draft_preview
            FROM leads_raw WHERE {user_cond} AND email_draft IS NOT NULL {date_cond}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, all_params + [per_page, offset])

    if card_type == 'bounce_detail':
        records = bounce_records
        result = {
            "card_type": card_type,
            "total": total,
            "page": page,
            "per_page": per_page,
            "records": records,
            "company_breakdown": company_breakdown
        }
    else:
        rows = cur.fetchall()
        records = [dict(r) for r in rows]
        result = {
            "card_type": card_type,
            "total": total,
            "page": page,
            "per_page": per_page,
            "records": records
        }

    if card_type == 'classified':
        try:
            cur.execute(f"SELECT followup_status, COUNT(*) as cnt FROM leads_raw WHERE {user_cond} AND persona IS NOT NULL AND persona != '' {date_cond} GROUP BY followup_status", all_params)
            followup_summary = [dict(r) for r in cur.fetchall()]
            result["followup_summary"] = followup_summary
        except:
            pass

    cur.close()
    conn.close()

    return result
