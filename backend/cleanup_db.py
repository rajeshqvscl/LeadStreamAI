import psycopg2
from app.database import get_db_connection

def clean():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Delete bad records
        bads = ['test', 'dummy', 'example', 'sample', 'mock', 'noreply', 'noemail', 'unknown']
        domains = ['@test.com', '@dummy.com', '@example.com']
        
        deleted_bad = 0
        for bk in bads:
            cur.execute("DELETE FROM leads_raw WHERE email ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s", (f"%{bk}%", f"%{bk}%", f"%{bk}%"))
            deleted_bad += cur.rowcount
            
        for dom in domains:
            cur.execute("DELETE FROM leads_raw WHERE email ILIKE %s", (f"%{dom}",))
            deleted_bad += cur.rowcount

        exes = ['ex-', 'former', 'previous', 'past', 'advisor', 'advisory', 'retired', 'board member', 'emeritus']
        for ex in exes:
            cur.execute("DELETE FROM leads_raw WHERE COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', persona, '') ILIKE %s", (f"%{ex}%",))
            deleted_bad += cur.rowcount

        # 2. Delete missing mandatory items
        cur.execute("DELETE FROM leads_raw WHERE (first_name IS NULL OR first_name = '') AND (last_name IS NULL OR last_name = '')")
        deleted_bad += cur.rowcount
        cur.execute("DELETE FROM leads_raw WHERE company_name IS NULL OR company_name = ''")
        deleted_bad += cur.rowcount
        cur.execute("DELETE FROM leads_raw WHERE (email IS NULL OR email = '') AND (linkedin_url IS NULL OR linkedin_url = '')")
        deleted_bad += cur.rowcount
        
        # 3. Deduplicate
        cur.execute("""
            DELETE FROM leads_raw a USING (
                SELECT MIN(ctid) as ctid, email
                FROM leads_raw 
                WHERE email IS NOT NULL AND email != ''
                GROUP BY email HAVING COUNT(*) > 1
            ) b
            WHERE a.email = b.email AND a.ctid <> b.ctid
        """)
        deleted_dupes = cur.rowcount
        
        cur.execute("""
            DELETE FROM leads_raw a USING (
                SELECT MIN(ctid) as ctid, linkedin_url
                FROM leads_raw 
                WHERE linkedin_url IS NOT NULL AND linkedin_url != ''
                GROUP BY linkedin_url HAVING COUNT(*) > 1
            ) b
            WHERE a.linkedin_url = b.linkedin_url AND a.ctid <> b.ctid
        """)
        deleted_dupes += cur.rowcount
        
        conn.commit()
        print(f"Cleanup complete. Deleted {deleted_bad} bad/invalid records, and {deleted_dupes} structural duplicates.")
        
        cur.close()
        conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    clean()
