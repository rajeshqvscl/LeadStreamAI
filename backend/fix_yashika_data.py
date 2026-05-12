from app.database import get_db_connection

def fix_yashika_leads():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Find Yashika's ID
        cur.execute("SELECT id FROM users WHERE username ILIKE 'yashika'")
        user = cur.fetchone()
        if not user:
            print("Yashika not found")
            return
            
        uid = user[0]
        print(f"Fixing leads for Yashika (ID: {uid})...")
        
        # 2. Update all her leads to be INVESTOR
        cur.execute("""
            UPDATE leads_raw 
            SET lead_type = 'INVESTOR',
                sector = COALESCE(sector, 'Investor - General'),
                updated_at = NOW()
            WHERE user_id = %s
            AND (LOWER(lead_type) != 'investor' OR lead_type IS NULL)
        """, (uid,))
        
        count = cur.rowcount
        conn.commit()
        print(f"Successfully updated {count} leads to INVESTOR.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_yashika_leads()
