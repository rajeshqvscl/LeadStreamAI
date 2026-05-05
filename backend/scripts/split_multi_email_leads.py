import os
import psycopg2
import psycopg2.extras
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv('app/.env', override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

def split_leads():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in .env")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Find leads with potentially concatenated emails (multiple @ symbols)
    print("🔍 Searching for leads with multiple email addresses...")
    cur.execute("SELECT * FROM leads_raw WHERE email LIKE '%@%@%';")
    leads = cur.fetchall()

    if not leads:
        print("✅ No leads with concatenated emails found.")
        cur.close()
        conn.close()
        return

    print(f"📦 Found {len(leads)} leads to process.")

    # Email regex pattern
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|org|net|co|in|ai|io|gov|edu|me|uk|ca|au|de|fr|jp|biz|info|us|eu)'
    
    split_count = 0
    new_leads_count = 0

    # Get all column names to copy data
    cur.execute("SELECT * FROM leads_raw LIMIT 0;")
    cols = [desc[0] for desc in cur.description]
    skip_cols = ['id', 'created_at', 'updated_at', 'email']
    copy_cols = [c for c in cols if c not in skip_cols]

    for lead in leads:
        original_id = lead['id']
        original_email_str = lead['email']
        
        # Extract all valid emails
        found_emails = re.findall(email_regex, original_email_str, re.IGNORECASE)
        
        if len(found_emails) <= 1:
            continue
            
        print(f"🧵 Splitting Lead {original_id}: Found {len(found_emails)} emails in '{original_email_str}'")
        
        # 1. Update the original lead with the first email
        cur.execute("UPDATE leads_raw SET email = %s, updated_at = NOW() WHERE id = %s", (found_emails[0], original_id))
        
        # 2. Create new leads for the remaining emails
        for extra_email in found_emails[1:]:
            col_names = ", ".join(copy_cols + ['email'])
            placeholders = ", ".join(["%s"] * (len(copy_cols) + 1))
            
            values = [lead[c] for c in copy_cols] + [extra_email]
            
            cur.execute(f"INSERT INTO leads_raw ({col_names}) VALUES ({placeholders})", values)
            new_leads_count += 1
            
        split_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✨ Done! Split {split_count} original leads and created {new_leads_count} new lead records.")

if __name__ == "__main__":
    split_leads()
