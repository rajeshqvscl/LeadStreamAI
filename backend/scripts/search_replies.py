import sys
import os

sys.path.append(os.getcwd())

from app.services.google_service import get_gmail_service

def search_replies(user_id):
    service = get_gmail_service(user_id)
    if not service: return
    
    # Search for emails from the leads we found earlier
    leads = ['harshbisht180@gmail.com', 'harsh.b@qvscl.com']
    for email in leads:
        print(f"Searching for replies from {email}...")
        results = service.users().messages().list(userId='me', q=f'from:{email}').execute()
        messages = results.get('messages', [])
        print(f"Found {len(messages)} messages.")
        for m in messages:
            msg = service.users().messages().get(userId='me', id=m['id'], format='metadata').execute()
            print(f"  - Subject: {msg.get('snippet')[:50]}... (Labels: {msg.get('labelIds')})")

if __name__ == "__main__":
    search_replies(9)
