import psycopg2
import psycopg2.extras
from app.database import get_db_connection
import csv
import io
from datetime import datetime

def get_all_family_offices():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get offices with lead counts
    query = """
    SELECT fo.*, COUNT(l.id) as count 
    FROM family_offices fo
    LEFT JOIN leads_raw l ON fo.name = l.family_office_name
    GROUP BY fo.id
    ORDER BY fo.name ASC
    """
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_family_office_by_id(office_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    query = "SELECT * FROM family_offices WHERE id = %s"
    cur.execute(query, (office_id,))
    row = cur.fetchone()
    
    if row:
        # Get lead count
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE family_office_name = %s", (row['name'],))
        row['count'] = cur.fetchone()['count']
        
    cur.close()
    conn.close()
    return row

def sync_from_csv(csv_content):
    f = io.StringIO(csv_content)
    reader = csv.DictReader(f)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    count = 0
    for row in reader:
        name = row.get('Name') or row.get('name')
        if not name:
            continue
            
        location = row.get('Location') or row.get('location') or ""
        category = row.get('Category') or row.get('category') or row.get('Sector') or row.get('sector') or ""
        strategic_fit = row.get('Strategic Fit') or row.get('strategic_fit') or "N/A Fit"
        
        query = """
        INSERT INTO family_offices (name, location, category, strategic_fit, last_synced)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            location = EXCLUDED.location,
            category = EXCLUDED.category,
            strategic_fit = EXCLUDED.strategic_fit,
            last_synced = EXCLUDED.last_synced
        """
        cur.execute(query, (name, location, category, strategic_fit, datetime.now()))
        count += 1
        
    conn.commit()
    cur.close()
    conn.close()
    return count

def bulk_delete_office_leads():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Delete leads that are associated with a family office
    cur.execute("DELETE FROM leads_raw WHERE family_office_name IS NOT NULL AND family_office_name != ''")
    
    conn.commit()
    cur.close()
    conn.close()

def get_office_leads(office_name):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    query = "SELECT * FROM leads_raw WHERE family_office_name = %s ORDER BY created_at DESC"
    cur.execute(query, (office_name,))
    rows = cur.fetchall()
    
    cur.close()
    conn.close()
    return rows
