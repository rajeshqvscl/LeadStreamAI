from fastapi import APIRouter
from app.database import get_db_connection
import psycopg2.extras

router = APIRouter()

@router.get("/dashboard/stats")
def get_dashboard_stats():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("SELECT COUNT(*) as total FROM leads_raw")
    total_leads = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as valid FROM leads_raw WHERE validation_status = 'VALID'")
    valid_leads = cur.fetchone()['valid']
    
    cur.execute("SELECT COUNT(*) as classified FROM leads_raw WHERE persona IS NOT NULL AND persona != ''")
    classified = cur.fetchone()['classified']
    
    cur.execute("SELECT COUNT(*) as pending FROM leads_raw WHERE email_status = 'PENDING_APPROVAL' OR email_status = 'pending'")
    pending = cur.fetchone()['pending']
    
    cur.execute("SELECT COUNT(*) as sent FROM leads_raw WHERE email_status = 'SENT'")
    sent = cur.fetchone()['sent']
    
    cur.execute("SELECT persona, COUNT(*) as count FROM leads_raw WHERE persona IS NOT NULL GROUP BY persona")
    persona_rows = cur.fetchall()
    persona_data = {}
    for r in persona_rows:
        if r['persona']:
            persona_data[r['persona']] = r['count']
        
    cur.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 7")
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
