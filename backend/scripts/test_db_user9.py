import psycopg2
from app.database import get_db_connection

def text_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Base counts
    cur.execute("SELECT user_id, COUNT(*) FROM leads_raw WHERE source = 'bulk' GROUP BY user_id")
    print("User IDs with bulk source:", cur.fetchall())
    
    # 2. Strict whitelist filtering condition mimicking get_leads
    query_strict = """
        SELECT COUNT(*)
        FROM leads_raw 
        WHERE source = 'bulk' AND user_id = 9
        AND (first_name IS NOT NULL OR last_name IS NOT NULL) AND (first_name != '' OR last_name != '')
        AND company_name IS NOT NULL AND company_name != ''
        AND ((email IS NOT NULL AND email != '') OR (linkedin_url IS NOT NULL AND linkedin_url != ''))
        AND COALESCE(email, '') !~* 'test|dummy|example|sample|mock|noreply|noemail|unknown'
        AND COALESCE(email, '') !~* '@(test|dummy|example)\.com$'
        AND COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') !~* 'ex-|former|previous|past|advisor|advisory|retired|board member|emeritus'
        AND (
            COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') = '' 
            OR COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') = 'OTHER' 
            OR COALESCE(designation, raw_payload->>'current_title', raw_payload->>'Designation', raw_payload->>'designation', raw_payload->>'Title', raw_payload->>'Job Title', raw_payload->>'Role', persona, '') ~* 'ceo|founder|co-founder|managing director|partner|owner|president'
        )
    """
    cur.execute(query_strict)
    print("Strict filter passing for user 9:", cur.fetchone()[0])
    
    # For user 5
    cur.execute(query_strict.replace("user_id = 9", "user_id = 1"))
    print("Strict filter passing for user 1:", cur.fetchone()[0])

if __name__ == "__main__":
    text_db()
