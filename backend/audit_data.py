from app.database import get_db_connection
import psycopg2.extras

def check_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    print("--- Activity Log Action Counts ---")
    cur.execute("SELECT action, COUNT(*) FROM activity_log GROUP BY action")
    for row in cur.fetchall():
        print(f"{row['action']}: {row['count']}")
        
    print("\n--- Leads Created Counts (Total) ---")
    cur.execute("SELECT COUNT(*) FROM leads_raw")
    print(f"Total leads: {cur.fetchone()[0]}")
    
    print("\n--- Users Role Counts ---")
    cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
    for row in cur.fetchall():
        print(f"{row['role']}: {row['count']}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_data()
