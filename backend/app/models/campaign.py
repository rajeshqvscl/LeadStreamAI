import psycopg2
import psycopg2.extras
from app.database import get_db_connection
from datetime import datetime

def create_campaign(data):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    query = """
    INSERT INTO campaigns (
        name, description, tone, target_industry, target_persona, 
        subject, html_body, context_prompt, strategy_prompt, is_active, user_id, user_name, target_companies
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING *
    """
    params = (
        data.get('name'), data.get('description'), data.get('tone', 'professional'),
        data.get('target_industry'), data.get('target_persona'),
        data.get('subject'), data.get('html_body'),
        data.get('context_prompt'), data.get('strategy_prompt'),
        data.get('is_active', True), data.get('user_id'), data.get('user_name'), data.get('target_companies')
    )
    
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        conn.commit()
        return row
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def get_campaigns(limit=10, offset=0, active_only=False, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    where_clause = "WHERE user_id = %s" if user_id else "WHERE user_id IS NULL"
    params = [user_id] if user_id else []
    
    if active_only:
        where_clause += " AND is_active = TRUE"
    
    query = f"SELECT * FROM campaigns {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    # Add stats
    for row in rows:
        cur.execute("SELECT COUNT(*) FROM recipients WHERE campaign_id = %s", (row['id'],))
        row['total_recipients'] = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) FROM campaign_events WHERE campaign_id = %s AND event_type = 'OPEN'", (row['id'],))
        row['opens'] = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) FROM campaign_events WHERE campaign_id = %s AND event_type = 'CLICK'", (row['id'],))
        row['clicks'] = cur.fetchone()['count']
        
    cur.close()
    conn.close()
    return rows

def get_campaign_by_id(campaign_id, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    where_clause = "WHERE id = %s AND user_id = %s" if user_id else "WHERE id = %s AND user_id IS NULL"
    cur.execute(f"SELECT * FROM campaigns {where_clause}", (campaign_id, user_id) if user_id else (campaign_id,))
    row = cur.fetchone()
    
    if row:
        cur.execute("SELECT COUNT(*) FROM recipients WHERE campaign_id = %s", (campaign_id,))
        row['total_recipients'] = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) FROM campaign_events WHERE campaign_id = %s AND event_type = 'OPEN'", (campaign_id,))
        row['opens'] = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) FROM campaign_events WHERE campaign_id = %s AND event_type = 'CLICK'", (campaign_id,))
        row['clicks'] = cur.fetchone()['count']
        if row['total_recipients'] > 0:
            row['open_rate'] = (row['opens'] / row['total_recipients']) * 100
            row['click_rate'] = (row['clicks'] / row['total_recipients']) * 100
        else:
            row['open_rate'] = 0
            row['click_rate'] = 0
            
    cur.close()
    conn.close()
    return row

def update_campaign(campaign_id, data, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    fields = []
    params = []
    for key, value in data.items():
        if key in ['name', 'description', 'tone', 'target_industry', 'target_persona', 
                  'subject', 'html_body', 'context_prompt', 'strategy_prompt', 'is_active', 'target_companies']:
            fields.append(f"{key} = %s")
            params.append(value)
            
    if not fields:
        cur.close()
        conn.close()
        return None
        
    fields.append("updated_at = NOW()")
    where_clause = "WHERE id = %s AND user_id = %s" if user_id else "WHERE id = %s AND user_id IS NULL"
    params.extend([campaign_id, user_id] if user_id else [campaign_id])
    
    query = f"UPDATE campaigns SET {', '.join(fields)} {where_clause} RETURNING *"
    
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        conn.commit()
        return row
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def delete_campaign(campaign_id, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    where_clause = "WHERE id = %s AND user_id = %s" if user_id else "WHERE id = %s AND user_id IS NULL"
    try:
        cur.execute(f"DELETE FROM campaigns {where_clause}", (campaign_id, user_id) if user_id else (campaign_id,))
        success = cur.rowcount > 0
        conn.commit()
        return success
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
