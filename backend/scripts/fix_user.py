import psycopg2
from app.database import get_db_connection

def fix():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("UPDATE leads_raw SET user_id = 1 WHERE source = 'bulk' AND user_id = 2")
        conn.commit()
        print(f"Updated {cur.rowcount} rows to user_id=1")
        
        cur.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    fix()
