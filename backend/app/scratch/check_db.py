from app.database import get_db_connection
import psycopg2

def check_duplicates():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("Checking for duplicates on (email, COALESCE(user_id, -1))...")
    
    # Check for duplicates
    query = """
        SELECT email, COALESCE(user_id, -1), COUNT(*)
        FROM leads_raw
        GROUP BY email, COALESCE(user_id, -1)
        HAVING COUNT(*) > 1;
    """
    
    cur.execute(query)
    duplicates = cur.fetchall()
    
    if not duplicates:
        print("No duplicates found.")
    else:
        print(f"Found {len(duplicates)} duplicate sets:")
        for email, uid, count in duplicates:
            print(f"  Email: {email}, UserID: {uid}, Count: {count}")
            
    # Check if the index exists
    print("\nChecking if index 'leads_raw_email_user_unique' exists...")
    cur.execute("""
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'leads_raw_email_user_unique' AND n.nspname = 'public';
    """)
    if cur.fetchone():
        print("Index exists!")
    else:
        print("Index NOT found.")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    try:
        check_duplicates()
    except Exception as e:
        print(f"Error: {e}")
