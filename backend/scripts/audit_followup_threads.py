"""Show exactly what the user sees: all Kajal (user 3) messages to sravanthi.m@qvscl.com with threads."""
import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path('app/.env'))
from app.services.google_service import get_gmail_service

service = get_gmail_service(3)

q = 'to:sravanthi.m@qvscl.com'
res = service.users().messages().list(userId='me', q=q, maxResults=40).execute()
msgs = res.get('messages', [])
print(f'Messages to sravanthi.m@qvscl.com in Kajal mailbox: {len(msgs)}')
for m in msgs:
    detail = service.users().messages().get(
        userId='me', id=m['id'], format='metadata',
        metadataHeaders=['Subject', 'Date', 'From', 'Message-ID', 'In-Reply-To']
    ).execute()
    hdrs = {h['name'].lower(): h['value'] for h in detail.get('payload', {}).get('headers', [])}
    print(f'  thread={detail.get("threadId")}')
    print(f'    date={hdrs.get("date")}')
    print(f'    subj={str(hdrs.get("subject"))[:80]}')
    print(f'    in-reply-to={str(hdrs.get("in-reply-to"))[:70]}')
    print()
