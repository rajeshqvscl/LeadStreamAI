import os
import re
from app.services.google_service import get_gmail_service, extract_attachments
from app.database import get_db_connection

def fix_it():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, user_id FROM leads_raw WHERE email = 'harsh.b@qvscl.com'")
    lead = cur.fetchone()
    if not lead:
        print("Lead not found.")
        return
        
    email = lead['email']
    user_id = lead['user_id']
    
    print(f"Finding PDF for {email} (user_id: {user_id})")
    try:
        service = get_gmail_service(user_id)
        # Search for messages with attachments from this email
        query = f"from:{email} has:attachment"
        results = service.users().messages().list(userId='me', q=query, maxResults=5).execute()
        messages = results.get('messages', [])
        
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            payload = msg_data.get('payload', {})
            attachments = extract_attachments(service, msg['id'], payload)
            pdf_attachment = next((att for att in attachments if att['filename'].lower().endswith('.pdf')), None)
            
            if pdf_attachment:
                os.makedirs("static/pitch_decks", exist_ok=True)
                safe_filename = "".join(c for c in pdf_attachment['filename'] if c.isalnum() or c in "._-").replace(" ", "_")
                file_path = f"static/pitch_decks/{msg['id']}_{safe_filename}"
                with open(file_path, "wb") as f:
                    f.write(pdf_attachment['data'])
                
                base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                pitch_deck_url = f"{base_url}/{file_path}"
                print(f"Updating DB with: {pitch_deck_url}")
                cur.execute("UPDATE leads_raw SET pitch_deck_url = %s WHERE id = %s", (pitch_deck_url, lead['id']))
                conn.commit()
                print("Success.")
                break
        else:
            print("No PDF attachment found in their emails.")
            
    except Exception as e:
        print("Error:", e)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    fix_it()
