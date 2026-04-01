import psycopg2
import psycopg2.extras
from app.database import get_db_connection
import csv
import io
from datetime import datetime

def get_all_family_offices(search_query=None, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Offices are global, but lead counts are isolated
    leads_where = "AND l.user_id = %s" if user_id else "AND l.user_id IS NULL"
    
    query_params = []
    if user_id:
        query_params.append(user_id)
        
    where_clause = "WHERE 1=1"
    if search_query:
        where_clause += " AND (fo.name ILIKE %s OR fo.location ILIKE %s OR fo.category ILIKE %s)"
        s = f"%{search_query}%"
        query_params.extend([s, s, s])
    
    query = f"""
    SELECT fo.*, COUNT(l.id) as count 
    FROM family_offices fo
    LEFT JOIN leads_raw l ON fo.name = l.family_office_name {leads_where}
    {where_clause}
    GROUP BY fo.id
    ORDER BY fo.name ASC
    """
    cur.execute(query, query_params)
    rows = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows

def get_family_office_by_id(office_id, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Office is global
    cur.execute("SELECT * FROM family_offices WHERE id = %s", (office_id,))
    row = cur.fetchone()
    
    if row:
        row = dict(row)
        l_where = "WHERE family_office_name = %s AND user_id = %s" if user_id else "WHERE family_office_name = %s AND user_id IS NULL"
        cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {l_where}", (row['name'], user_id) if user_id else (row['name'],))
        row['count'] = cur.fetchone()['count']
        
    cur.close()
    conn.close()
    return row

def sync_from_csv(csv_content, user_id=None):
    f = io.StringIO(csv_content)
    reader = csv.DictReader(f)
    conn = get_db_connection()
    cur = conn.cursor()
    count = 0
    for row in reader:
        name = row.get('Family Office Name') or row.get('Name') or ""
        if not name: continue
        location = row.get('Headquarters') or row.get('Location') or ""
        category = row.get('Investment Sectors') or row.get('Category') or ""
        strategic_fit = row.get('Ticket Size') or row.get('Strategic Fit') or "N/A Fit"
        # Syncing is global (ON CONFLICT just updates)
        cur.execute("""
            INSERT INTO family_offices (name, location, category, strategic_fit, last_synced)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET location=EXCLUDED.location, last_synced=EXCLUDED.last_synced
        """, (name, location, category, strategic_fit, datetime.now()))
        count += 1
    conn.commit()
    cur.close()
    conn.close()
    return count

def bulk_delete_office_leads(user_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    where_clause = "WHERE family_office_name IS NOT NULL AND user_id = %s" if user_id else "WHERE family_office_name IS NOT NULL AND user_id IS NULL"
    cur.execute(f"DELETE FROM leads_raw {where_clause}", (user_id,) if user_id else ())
    conn.commit()
    cur.close()
    conn.close()

def get_office_leads(office_name, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    where_clause = "WHERE family_office_name = %s AND user_id = %s" if user_id else "WHERE family_office_name = %s AND user_id IS NULL"
    cur.execute(f"SELECT * FROM leads_raw {where_clause} ORDER BY created_at DESC", (office_name, user_id) if user_id else (office_name,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def update_family_office(office_id, data, user_id=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    fields = []
    values = []
    for key, value in data.items():
        if key in ['location', 'category', 'strategic_fit']:
            fields.append(f"{key} = %s")
            values.append(value)
    if not fields:
        cur.close()
        conn.close()
        return None
    # Update is global
    values.append(office_id)
    query = f"UPDATE family_offices SET {', '.join(fields)} WHERE id = %s RETURNING *"
    cur.execute(query, values)
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return row
