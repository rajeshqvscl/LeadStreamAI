from app.database import get_db_connection
import psycopg2.extras

def get_yashika_companies():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Find Yashika's ID
        cur.execute("SELECT id FROM users WHERE username ILIKE 'yashika'")
        user = cur.fetchone()
        if not user:
            print("Yashika not found")
            return
            
        uid = user['id']
        
        # 2. Get distinct company names
        cur.execute("""
            SELECT DISTINCT company_name 
            FROM leads_raw 
            WHERE user_id = %s 
            AND company_name IS NOT NULL 
            AND company_name != ''
            ORDER BY company_name
        """, (uid,))
        
        companies = cur.fetchall()
        print(f"Companies Yashika works on ({len(companies)} total):")
        for c in companies:
            print(f"- {c['company_name']}")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_yashika_companies()
