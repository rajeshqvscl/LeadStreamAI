import psycopg2
import psycopg2.extras
from app.database import get_db_connection
from datetime import datetime

def create_campaign(data):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    query = """
    INSERT INTO campaigns (
        name, description, tone, target_industry, target_persona, 
        subject, html_body, context_prompt, strategy_prompt, is_active
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING *
    """
    params = (
        data.get('name'), data.get('description'), data.get('tone', 'professional'),
        data.get('target_industry'), data.get('target_persona'),
        data.get('subject'), data.get('html_body'),
        data.get('context_prompt'), data.get('strategy_prompt'),
        data.get('is_active', True)
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

def get_campaigns(limit=10, offset=0, active_only=False):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    query = "SELECT * FROM campaigns"
    params = []
    if active_only:
        query += " WHERE is_active = TRUE"
    
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    # Add stats for each campaign
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

def get_campaign_by_id(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
    row = cur.fetchone()
    
    if row:
        cur.execute("SELECT COUNT(*) FROM recipients WHERE campaign_id = %s", (campaign_id,))
        row['total_recipients'] = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) FROM campaign_events WHERE campaign_id = %s AND event_type = 'OPEN'", (campaign_id,))
        row['opens'] = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) FROM campaign_events WHERE campaign_id = %s AND event_type = 'CLICK'", (campaign_id,))
        row['clicks'] = cur.fetchone()['count']
        
        # Calculate rates
        if row['total_recipients'] > 0:
            row['open_rate'] = (row['opens'] / row['total_recipients']) * 100
            row['click_rate'] = (row['clicks'] / row['total_recipients']) * 100
        else:
            row['open_rate'] = 0
            row['click_rate'] = 0
            
    cur.close()
    conn.close()
    return row

def update_campaign(campaign_id, data):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    fields = []
    params = []
    for key, value in data.items():
        if key in ['name', 'description', 'tone', 'target_industry', 'target_persona', 
                  'subject', 'html_body', 'context_prompt', 'strategy_prompt', 'is_active']:
            fields.append(f"{key} = %s")
            params.append(value)
            
    if not fields:
        cur.close()
        conn.close()
        return None
        
    fields.append("updated_at = NOW()")
    params.append(campaign_id)
    
    query = f"UPDATE campaigns SET {', '.join(fields)} WHERE id = %s RETURNING *"
    
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

def delete_campaign(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))
        success = cur.rowcount > 0
        conn.commit()
        return success
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
