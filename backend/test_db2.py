import psycopg2
from app.database import get_db_connection

def text_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM leads_raw WHERE source = 'bulk'")
    print("Total bulk leads in DB:", cur.fetchone()[0])
    
    cur.execute("""
        SELECT raw_payload FROM leads_raw 
        WHERE source = 'bulk'
        LIMIT 5
    """)
    print("Sample payloads:", [r[0] for r in cur.fetchall()])

if __name__ == "__main__":
    text_db()
