from app.database import get_db_connection
import json

def check():
    conn = get_db_connection()
    cur = conn.cursor()
    
    tables = [
        "leads_raw", "campaigns", "prompts", "family_offices", 
        "company_registry", "search_history", "activity_log",
        "users", "unsubscribe_list"
    ]
    
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"{table}: {count} rows")
        except Exception as e:
            print(f"{table}: Error - {e}")
            conn.rollback()
            
    # Check for leads without user_id
    try:
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE user_id IS NULL")
        null_count = cur.fetchone()[0]
        print(f"leads_raw (user_id IS NULL): {null_count} rows")
    except: pass
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check()
