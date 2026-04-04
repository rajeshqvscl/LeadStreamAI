import psycopg2
from app.database import get_db_connection

def fix():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("UPDATE leads_raw SET source = 'bulk' WHERE source = 'import'")
        conn.commit()
        print(f"Updated {cur.rowcount} rows from 'import' to 'bulk'")
        
        cur.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    fix()
