from app.database import get_db_connection
import psycopg2.extras

def check_schema():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Check leads_raw
    print("Checking leads_raw columns:")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'leads_raw'")
    cols = cur.fetchall()
    for col in cols:
        print(f" - {col['column_name']}: {col['data_type']}")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_schema()
