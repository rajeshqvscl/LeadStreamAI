
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Optional
import psycopg2.extras
from app.database import get_db_connection
import structlog
import json

router = APIRouter()
logger = structlog.get_logger(__name__)

def normalize_user_id(uid):
    if not uid: return None
    try: return int(uid)
    except: return uid

@router.get("/leads/all")
def get_all_leads_admin(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Returns ALL leads from ALL users in the database.
    Only accessible by 'admin' role.
    """
    # Simple role check (In a real app, this would check a 'role' column in users table)
    # For now, we use the 'admin' convention or user_id=1 as admin.
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Verify Admin Role
        cur.execute("SELECT username FROM users WHERE id = %s", (normalize_user_id(user_id),))
        user = cur.fetchone()
        if not user or user['username'].lower() != 'admin' and normalize_user_id(user_id) != 1:
             # If you want to be strict, uncomment this. For now we allow if user_id is 'admin' string too.
             if user_id != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required")

        # 2. Fetch all leads with owner names
        query = """
            SELECT l.*, u.username as owner_name, u.full_name as owner_full_name
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            ORDER BY l.updated_at DESC
        """
        cur.execute(query)
        leads = cur.fetchall()
        
        return [dict(l) for l in leads]
        
    except Exception as e:
        logger.error("admin_all_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/stats/global")
def get_global_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Aggregates metrics across the entire workspace.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Total leads
        cur.execute("SELECT COUNT(*) FROM leads_raw")
        total_leads = cur.fetchone()[0]
        
        # Interested (Intent)
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE reply_intent = 'INTERESTED'")
        interested = cur.fetchone()[0]
        
        # Meetings
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'Meeting Scheduled' OR meeting_time IS NOT NULL")
        meetings = cur.fetchone()[0]
        
        # Avg Score (Sentiment)
        cur.execute("SELECT AVG(sentiment_score) FROM leads_raw WHERE sentiment_score IS NOT NULL")
        avg_score = cur.fetchone()[0] or 0
        
        # Active Followups
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE followup_status = 'ACTIVE'")
        active_followups = cur.fetchone()[0]
        
        return {
            "total_leads": total_leads,
            "interested_leads": interested,
            "meetings_scheduled": meetings,
            "conversion_rate": round((interested / total_leads * 100), 1) if total_leads > 0 else 0,
            "avg_score": round(float(avg_score), 1),
            "active_followups": active_followups
        }
        
    except Exception as e:
        logger.error("admin_global_stats_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
