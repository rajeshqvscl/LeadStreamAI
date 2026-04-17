from app.database import get_db_connection

def get_index_def():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT indexdef 
        FROM pg_indexes 
        WHERE indexname = 'leads_raw_email_user_unique';
    """)
    result = cur.fetchone()
    if result:
        print(f"Index Definition:\n{result['indexdef']}")
    else:
        print("Index not found.")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    get_index_def()
