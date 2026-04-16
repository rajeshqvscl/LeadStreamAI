from fastapi import APIRouter, Header
from app.database import get_db_connection
import psycopg2.extras
from typing import Optional

router = APIRouter()

@router.get("/dashboard/stats")
def get_dashboard_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Base condition for data isolation
    # 'admin' literal header → sees ALL data (no user filter)
    is_admin = (str(user_id or '').lower() == 'admin')

    if is_admin:
        where_clause = "WHERE 1=1"
        params = ()
    elif user_id and user_id.strip():
        where_clause = "WHERE user_id = %s"
        params = (user_id,)
    else:
        where_clause = "WHERE user_id IS NULL"
        params = ()

    # Exclude bulk/csv_import sources from total_leads and pending counts
    leads_filter = "AND (source IS NULL OR source NOT IN ('bulk', 'csv_import'))"
    
    cur.execute(f"SELECT COUNT(*) as total FROM leads_raw {where_clause} {leads_filter}", params)
    total_leads = cur.fetchone()['total']
    
    cur.execute(f"SELECT COUNT(*) as valid FROM leads_raw {where_clause} AND validation_status = 'VALID' {leads_filter}", params)
    valid_leads = cur.fetchone()['valid']
    
    cur.execute(f"SELECT COUNT(*) as classified FROM leads_raw {where_clause} AND persona IS NOT NULL AND persona != '' {leads_filter}", params)
    classified = cur.fetchone()['classified']
    
    cur.execute(f"SELECT COUNT(*) as pending FROM leads_raw {where_clause} AND (email_status = 'PENDING_APPROVAL' OR email_status = 'pending') {leads_filter}", params)
    pending = cur.fetchone()['pending']
    
    cur.execute(f"SELECT COUNT(*) as sent FROM leads_raw {where_clause} AND email_status = 'SENT' {leads_filter}", params)
    sent = cur.fetchone()['sent'] or 0
    
    cur.execute(f"SELECT COUNT(*) as refined FROM leads_raw {where_clause} AND email_draft IS NOT NULL {leads_filter}", params)
    refined = cur.fetchone()['refined'] or 0

    # Company Registry Count — scoped to the logged-in user
    if is_admin:
        cur.execute("SELECT COUNT(*) as total FROM company_registry")
    elif user_id and user_id.strip():
        cur.execute("SELECT COUNT(*) as total FROM company_registry WHERE user_id = %s", (user_id,))
    else:
        cur.execute("SELECT COUNT(*) as total FROM company_registry WHERE user_id IS NULL")
    total_companies = cur.fetchone()['total'] or 0
    
    # Engagement Pulse - Joining with leads_raw to ensure user-isolation
    events_join = "JOIN leads_raw l ON ce.recipient_id = l.id"
    if is_admin:
        events_where = "WHERE 1=1"
    elif user_id and user_id.strip():
        events_where = "WHERE l.user_id = %s"
    else:
        events_where = "WHERE l.user_id IS NULL"
    
    cur.execute(f"SELECT COUNT(DISTINCT ce.recipient_id) as opens FROM campaign_events ce {events_join} {events_where} AND ce.event_type = 'OPEN'", params)
    unique_opens = cur.fetchone()['opens'] or 0
    
    cur.execute(f"SELECT COUNT(DISTINCT ce.recipient_id) as clicks FROM campaign_events ce {events_join} {events_where} AND ce.event_type = 'CLICK'", params)
    unique_clicks = cur.fetchone()['clicks'] or 0
    
    cur.execute(f"SELECT COUNT(*) as bounces FROM campaign_events ce {events_join} {events_where} AND ce.event_type = 'BOUNCE'", params)
    total_bounces = cur.fetchone()['bounces'] or 0
    
    # Unsubscribes (matching emails belonging to the user)
    cur.execute(f"SELECT COUNT(*) as unsubs FROM unsubscribe_list WHERE email IN (SELECT email FROM leads_raw {where_clause})", params)
    total_unsubs = cur.fetchone()['unsubs'] or 0

    # Data discovery metrics for pulse fallback
    cur.execute(f"SELECT COUNT(*) as with_email FROM leads_raw {where_clause} AND email IS NOT NULL AND email != ''", params)
    with_email = cur.fetchone()['with_email'] or 0
    cur.execute(f"SELECT COUNT(*) as with_linkedin FROM leads_raw {where_clause} AND linkedin_url IS NOT NULL AND linkedin_url != ''", params)
    with_linkedin = cur.fetchone()['with_linkedin'] or 0

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

    cur.execute(f"SELECT persona, COUNT(*) as count FROM leads_raw {where_clause} AND persona IS NOT NULL GROUP BY persona", params)

    persona_rows = cur.fetchall()
    persona_data = {}
    for r in persona_rows:
        if r['persona']:
            persona_data[r['persona']] = r['count']
        
    cur.execute(f"SELECT * FROM activity_log {where_clause} ORDER BY created_at DESC LIMIT 7", params)
    logs_rows = cur.fetchall()
    recent_logs = []
    for row in logs_rows:
        recent_logs.append(dict(row))

        
    cur.close()
    conn.close()

    return {
        "total_leads": total_leads,
        "valid_leads": valid_leads,
        "classified": classified,
        "pending": pending,
        "sent": sent,
        "refined": refined,
        "daily_sent_count": sent,
        "daily_limit": 100,
        "open_rate": open_rate,
        "click_rate": click_rate,
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
