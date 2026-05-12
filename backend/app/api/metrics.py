from fastapi import APIRouter, Header
from typing import Optional
from app.database import get_db_connection
import psycopg2.extras
from datetime import datetime, timezone

router = APIRouter(tags=["Metrics"])

@router.get("/metrics")
def get_metrics(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Get metrics matching the requested Reports & Analytics dashboard."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Base condition: If user_id is provided, filter by it. Otherwise show ALL.
    if user_id and user_id != 'all':
        where_clause = "WHERE user_id = %s"
        params = (user_id,)
    else:
        where_clause = "WHERE 1=1"
        params = ()

    # Base counts from leads_raw
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause}", params)
    leads_count = cur.fetchone()['count'] or 0

    # Include Company Registry ingestions in the total ingestion count
    # This addresses cases where users have imported thousands of companies but only a few leads
    reg_where = "WHERE user_id = %s" if user_id and user_id != 'all' else "WHERE 1=1"
    cur.execute(f"SELECT COUNT(*) as count FROM company_registry {reg_where}", params)
    registry_count = cur.fetchone()['count'] or 0
    
    total_leads = leads_count + registry_count

    # Accuracy Flow: Use leads that have rag_intelligence as "Verified"
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND rag_intelligence IS NOT NULL", params)
    valid_leads = cur.fetchone()['count'] or 0

    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND (lead_type IS NOT NULL AND lead_type != '')", params)
    classified_leads = cur.fetchone()['count'] or 0

    cur.execute(f"SELECT COUNT(*) as count FROM campaigns {where_clause} AND is_active = TRUE", params)
    active_campaigns = cur.fetchone()['count'] or 0

    # Isolated via join with campaigns OR from leads_raw status
    if user_id and user_id != 'all':
        join_where = "WHERE c.user_id = %s"
    else:
        join_where = "WHERE 1=1"
    
    # 1. Sent: From campaign_events OR leads_raw where status is SENT/OPENED/REPLIED/etc.
    cur.execute(f"""
        SELECT 
            (SELECT COUNT(DISTINCT e.recipient_id) FROM campaign_events e JOIN campaigns c ON e.campaign_id = c.id {join_where} AND e.event_type = 'SENT') +
            (SELECT COUNT(*) FROM leads_raw {where_clause} AND email_status IN ('SENT', 'OPENED', 'REPLIED', 'Meeting Scheduled', 'Contacted', 'Interested'))
        as count
    """, params + params)
    sent = cur.fetchone()['count'] or 0
    
    # 2. Delivered: Usually Sent - Bounces
    cur.execute(f"SELECT COUNT(*) FROM leads_raw {where_clause} AND email_status = 'BOUNCED'", params)
    bounce_count = cur.fetchone()['count'] or 0
    delivered = max(sent - bounce_count, 0)
    
    # 3. Opens: From campaign_events OR leads_raw where status is OPENED/REPLIED/etc.
    cur.execute(f"""
        SELECT 
            (SELECT COUNT(DISTINCT e.recipient_id) FROM campaign_events e JOIN campaigns c ON e.campaign_id = c.id {join_where} AND e.event_type = 'OPEN') +
            (SELECT COUNT(*) FROM leads_raw {where_clause} AND email_status IN ('OPENED', 'REPLIED', 'Meeting Scheduled', 'Interested'))
        as count
    """, params + params)
    unique_opens = cur.fetchone()['count'] or 0
    
    # 4. Inbound Signals: From is_responded or status REPLIED
    cur.execute(f"SELECT COUNT(*) FROM leads_raw {where_clause} AND (is_responded = TRUE OR email_status IN ('REPLIED', 'Meeting Scheduled', 'Interested'))", params)
    unique_engaged = cur.fetchone()['count'] or 0
    unique_clicks = 0 # Fallback

    # Calculate Rates
    open_rate = (unique_opens / delivered * 100) if delivered > 0 else 0.0
    click_rate = (unique_clicks / delivered * 100) if delivered > 0 else 0.0
    ctr = (unique_clicks / unique_opens * 100) if unique_opens > 0 else 0.0
    unsub_rate = 0.0 # Fallback
    total_unsubs = 0 # Fallback
    bounce_rate = (bounce_count / sent * 100) if sent > 0 else 0.0
    engagement_rate = (unique_engaged / delivered * 100) if delivered > 0 else 0.0
    conversion_rate = (unique_engaged / total_leads * 100) if total_leads > 0 else 0.0

    # Persona breakdown -> Use lead_type
    cur.execute(f"SELECT COALESCE(lead_type, 'OTHER') as persona, COUNT(*) as count FROM leads_raw {where_clause} GROUP BY COALESCE(lead_type, 'OTHER')", params)
    persona_rows = cur.fetchall()
    persona_breakdown = { r['persona'].upper(): r['count'] for r in persona_rows }

    # Sector breakdown -> Use sector column
    cur.execute(f"SELECT COALESCE(sector, 'Other') as industry, COUNT(*) as count FROM leads_raw {where_clause} GROUP BY COALESCE(sector, 'Other') ORDER BY count DESC LIMIT 10", params)
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
    ''', params)
    country_rows = cur.fetchall()
    country_breakdown = { r['country']: r['count'] for r in country_rows }

    # Real-Time Inbound Signals
    cur.execute(f"""
        SELECT e.event_type as signal_type, e.created_at as time, e.user_agent as environment_data, l.email, l.first_name, l.last_name
        FROM campaign_events e
        JOIN recipients r ON e.recipient_id = r.id
        JOIN leads_raw l ON r.lead_id = l.id
        JOIN campaigns c ON e.campaign_id = c.id
        {join_where}
        ORDER BY e.created_at DESC
        LIMIT 10
    """, params)
    recent_signals = cur.fetchall()
    
    # Serialize datetime instances
    for sig in recent_signals:
        if sig['time']:
            sig['time'] = sig['time'].isoformat()
            
    if not recent_signals:
        recent_signals = []


    cur.close()
    conn.close()

    # Exact frontend-ready payload (matching Mailmergo style + dashboard fields)
    return {
        "total_leads": total_leads,
        "valid_leads": valid_leads,
        "invalid_leads": 0,
        "classified_leads": classified_leads,
        "active_campaigns": active_campaigns,
        
        "sent": sent,
        "delivered": delivered,
        "unique_opens": unique_opens,
        "unique_clicks": unique_clicks,
        "unique_engaged": unique_engaged,
        "bounces": bounce_count,
        "total_bounces": bounce_count,
        "unsubs": total_unsubs,
        "total_unsubs": total_unsubs,
        
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "ctr": round(ctr, 2),
        "unsub_rate": round(unsub_rate, 2),
        "bounce_rate": round(bounce_rate, 2),
        "engagement_rate": round(engagement_rate, 2),
        "conversion_rate": round(conversion_rate, 2),
        
        "persona_breakdown": persona_breakdown,
        "industry_breakdown": industry_breakdown,
        "country_breakdown": country_breakdown,
        "recent_signals": recent_signals,
        
        "timestamp": datetime.now(timezone.utc).isoformat()
    }





