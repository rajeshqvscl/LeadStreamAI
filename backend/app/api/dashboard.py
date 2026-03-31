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
    where_clause = "WHERE user_id = %s" if user_id else "WHERE user_id IS NULL"
    params = (user_id,) if user_id else ()

    cur.execute(f"SELECT COUNT(*) as total FROM leads_raw {where_clause}", params)
    total_leads = cur.fetchone()['total']
    
    cur.execute(f"SELECT COUNT(*) as valid FROM leads_raw {where_clause} AND validation_status = 'VALID'", params)
    valid_leads = cur.fetchone()['valid']
    
    cur.execute(f"SELECT COUNT(*) as classified FROM leads_raw {where_clause} AND persona IS NOT NULL AND persona != ''", params)
    classified = cur.fetchone()['classified']
    
    cur.execute(f"SELECT COUNT(*) as pending FROM leads_raw {where_clause} AND (email_status = 'PENDING_APPROVAL' OR email_status = 'pending')", params)
    pending = cur.fetchone()['pending']
    
    cur.execute(f"SELECT COUNT(*) as sent FROM leads_raw {where_clause} AND email_status = 'SENT'", params)
    sent = cur.fetchone()['sent']
    
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
        "conversion_rate": 12.5,
        "daily_sent_count": sent,
        "daily_limit": 1000,
        "open_rate": 45.2,
        "unique_opens": 39,
        "click_rate": 15.6,
        "unique_clicks": 13,
        "engagement_rate": 22.4,
        "bounce_rate": 2.1,
        "total_bounces": 1,
        "total_unsubs": 0,
        "unsub_rate": 0.0,
        "recent_logs": recent_logs,
        "persona_data": persona_data if persona_data else { "FOUNDER": 0, "INVESTOR": 0, "PARTNER": 0 }
    }
