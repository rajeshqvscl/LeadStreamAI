from app.database import get_db_connection
import psycopg2.extras

def check_yashika():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("SELECT id, username FROM users WHERE username ILIKE 'yashika'")
    user = cur.fetchone()
    if not user:
        print("Yashika not found")
        return
        
    uid = user['id']
    print(f"Yashika ID: {uid}")
    
    cur.execute("SELECT id, first_name, last_name, lead_type, persona, sector FROM leads_raw WHERE user_id = %s LIMIT 10", (uid,))
    leads = cur.fetchall()
    print("\nSample Leads for Yashika:")
    for l in leads:
        print(dict(l))
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_yashika()
