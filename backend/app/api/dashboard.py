from fastapi import APIRouter, Header
from app.database import get_db_connection
import psycopg2.extras
from typing import Optional

router = APIRouter()

@router.get("/dashboard/stats")
def get_dashboard_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    is_admin = (str(user_id or '').lower() == 'admin')

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
        act_cond = "user_id = %s"
        act_params = [resolved_id]
    else:
        user_cond = "user_id IS NULL"
        user_params = []
        act_cond = "1=1"
        act_params = []

    # Single query for all counts
    company_count_sql = user_cond if is_admin or resolved_id is not None else "1=1"
    cur.execute(f"""
        SELECT
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND is_responded = TRUE) AS total_leads,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND validation_status = 'VALID') AS valid_leads,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND persona IS NOT NULL AND persona != '') AS classified,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND (email_status = 'PENDING_APPROVAL' OR email_status = 'pending')) AS pending,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND email_status = 'SENT') AS sent,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND email_draft IS NOT NULL) AS refined,
            (SELECT COUNT(*) FROM company_registry WHERE {company_count_sql}) AS total_companies,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND email_status = 'OPENED') AS unique_opens,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND email_status = 'CLICKED') AS unique_clicks,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND email_status = 'BOUNCED') AS total_bounces,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND email IS NOT NULL AND email != '') AS with_email,
            (SELECT COUNT(*) FROM leads_raw WHERE {user_cond} AND linkedin_url IS NOT NULL AND linkedin_url != '') AS with_linkedin
    """, user_params * 12 if user_params else [])
    
    row = cur.fetchone()
    
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
    cur.execute(f"SELECT COUNT(*) as unsubs FROM unsubscribe_list WHERE email IN (SELECT email FROM leads_raw WHERE {user_cond})", user_params)
    total_unsubs = cur.fetchone()['unsubs'] or 0

    # Rate Calculations (using lead enrichment as fallback for pulse when no emails are sent)
    if sent > 0:
        open_rate = float(f"{(unique_opens / sent * 100):.1f}")
        click_rate = float(f"{(unique_clicks / sent * 100):.1f}")
        bounce_rate = float(f"{(total_bounces / sent * 100):.1f}")
        unsub_rate = float(f"{(total_unsubs / sent * 100):.1f}")
        engagement_rate = float(f"{((unique_opens + unique_clicks) / sent * 100):.1f}")
    else:
        # Fallback metrics to show discovery/enrichment "Pulse" before sending
        # Heat Delta = AI classification progress
        engagement_rate = float(f"{(classified / total_leads * 100):.1f}") if total_leads > 0 else 0.0
        # Open Rate fallback = Email discovery rate
        open_rate = float(f"{(with_email / total_leads * 100):.1f}") if total_leads > 0 else 0.0
        # Click Rate fallback = LinkedIn discovery rate
        click_rate = float(f"{(with_linkedin / total_leads * 100):.1f}") if total_leads > 0 else 0.0
        
        # Volume metrics update
        unique_opens = with_email
        unique_clicks = with_linkedin
        
        bounce_rate = 0.0
        unsub_rate = float(f"{(total_unsubs / total_leads * 100):.1f}") if total_leads > 0 else 0.0

    cur.execute(f"SELECT persona, COUNT(*) as count FROM leads_raw WHERE {user_cond} AND persona IS NOT NULL GROUP BY persona", user_params)

    persona_rows = cur.fetchall()
    persona_data = {}
    for r in persona_rows:
        if r['persona']:
            persona_data[r['persona']] = r['count']
        
    cur.execute(f"SELECT * FROM activity_log WHERE {act_cond} ORDER BY created_at DESC LIMIT 7", act_params)
    logs_rows = cur.fetchall()
    recent_logs = []
    for row in logs_rows:
        recent_logs.append(dict(row))

        
    # Count of emails sent today (using activity_log for accuracy, IST timezone)
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

    cur.close()
    conn.close()

    return {
        "total_leads": total_leads,
        "valid_leads": valid_leads,
        "classified": classified,
        "pending": pending,
        "sent": sent,
        "refined": refined,
        "daily_sent_count": sent_today,
        "today_followups": fup_today,
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
        "total_companies": total_companies
    }
