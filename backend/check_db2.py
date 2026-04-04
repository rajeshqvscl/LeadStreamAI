import psycopg2
from app.database import get_db_connection

def check():
    conn = get_db_connection()
    cur = conn.cursor()
    
    query3 = """
        SELECT id, COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') as title
        FROM leads_raw 
        WHERE source = 'bulk'
        AND (first_name IS NOT NULL OR last_name IS NOT NULL) AND (first_name != '' OR last_name != '')
        AND company_name IS NOT NULL AND company_name != ''
        AND ((email IS NOT NULL AND email != '') OR (linkedin_url IS NOT NULL AND linkedin_url != ''))
        AND COALESCE(email, '') !~* 'test|dummy|example|sample|mock|noreply|noemail|unknown'
        AND COALESCE(first_name, '') !~* 'test|dummy|example|sample|mock|noreply|noemail|unknown'
        AND COALESCE(last_name, '') !~* 'test|dummy|example|sample|mock|noreply|noemail|unknown'
        AND COALESCE(email, '') !~* '@(test|dummy|example)\.com$'
    """
    
    query_title_filter = query3 + """
        AND COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') !~* 'ex-|former|previous|past|advisor|advisory|retired|board member|emeritus'
        AND (
            COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') = '' 
            OR 
            COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') = 'OTHER' 
            OR 
            COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') ~* 'ceo|founder|co-founder|managing director|partner|owner|president'
        )
    """
    
    cur.execute(query_title_filter)
    res4 = cur.fetchall()
    print("PASSING TITLE FILTER:", [r['id'] for r in res4] if len(res4) > 0 else "0")
    
    query_user = query_title_filter + " AND user_id = 1"
    cur.execute(query_user)
    print("PASSING USER 1 FILTER:", len(cur.fetchall()))
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check()
