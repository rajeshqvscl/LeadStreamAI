import os
import datetime
import json
from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import psycopg2.extras
from app.database import get_db_connection

# Scopes required for the application
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/drive.file',
    'openid'
]

def get_google_flow(redirect_uri: Optional[str] = None):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    # Use the provided redirect_uri or fall back to the one in .env
    final_redirect_uri = redirect_uri or os.getenv("GOOGLE_REDIRECT_URI")
    
    client_config = {
        "web": {
            "client_id": client_id,
            "project_id": "leadstreamai",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [final_redirect_uri]
        }
    }
    
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=final_redirect_uri
    )

def get_user_credentials(user_id: int) -> Optional[Credentials]:
    """Retrieves and refreshes Google OAuth credentials for a user."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("""
            SELECT google_access_token, google_refresh_token, google_token_expiry 
            FROM users WHERE id = %s
        """, (user_id,))
        user = cur.fetchone()
        
        if not user or not user['google_refresh_token']:
            return None
            
        creds = Credentials(
            token=user['google_access_token'],
            refresh_token=user['google_refresh_token'],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=SCOPES
        )
        
        # Check if expired and refresh if necessary
        if creds.expired or (creds.expiry and creds.expiry < datetime.datetime.now(datetime.timezone.utc)):
            try:
                creds.refresh(Request())
            except Exception as e:
                # If refresh fails due to scope mismatch (invalid_scope), try refreshing with 
                # a minimal scope set that we know they likely have
                if "invalid_scope" in str(e).lower():
                    print(f"CRITICAL: Scope mismatch for user {user_id}. Re-authentication required.")
                    # Do not downgrade. Let the application handle the 401/403.
                    raise e
                else:
                    raise e

            # Save new tokens
            cur.execute("""
                UPDATE users 
                SET google_access_token = %s, 
                    google_token_expiry = %s 
                WHERE id = %s
            """, (creds.token, creds.expiry, user_id))
            conn.commit()
            
        return creds
    finally:
        cur.close()
        conn.close()

def get_gmail_service(user_id: int):
    creds = get_user_credentials(user_id)
    if not creds:
        return None
    # Disable discovery cache to avoid scope restriction bugs
    print(f"DEBUG: Building Gmail service for user {user_id} with SCOPES: {creds.scopes}")
    return build('gmail', 'v1', credentials=creds, static_discovery=False)

def get_calendar_service(user_id: int):
    creds = get_user_credentials(user_id)
    if not creds:
        return None
    return build('calendar', 'v3', credentials=creds, static_discovery=False)

def get_drive_service(user_id: int):
    creds = get_user_credentials(user_id)
    if not creds:
        return None
    return build('drive', 'v3', credentials=creds, static_discovery=False)

def register_gmail_watch(user_id: int):
    """Call Gmail watch() API for a specific user ID."""
    service = get_gmail_service(user_id)
    if not service:
        print(f"Watch failed: No credentials for user {user_id}")
        return None
        
    topic_name = os.getenv("GMAIL_WATCH_TOPIC")
    if not topic_name:
        print("Watch failed: GMAIL_WATCH_TOPIC not set in .env")
        return None
        
    try:
        request = {
            'labelIds': ['INBOX'],
            'topicName': topic_name
        }
        res = service.users().watch(userId='me', body=request).execute()
        print(f"Gmail watch dynamic registration successful for user {user_id}: {res}")
        return res
    except Exception as e:
        print(f"Error registering Gmail watch for user {user_id}: {e}")
        return None

def extract_message_body(payload: Dict[str, Any]) -> str:
    """
    Recursively extracts the body text from a Gmail message payload.
    Handles base64 padding and prioritizes plain text or HTML.
    """
    import base64
    
    def get_data(body):
        data = body.get('data', '')
        if not data: return ""
        try:
            # Standard padding fix: ensure length is a multiple of 4
            data = data.replace('-', '+').replace('_', '/')
            data += '=' * (-len(data) % 4)
            return base64.b64decode(data).decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Base64 decode error: {e}")
            return ""

    parts = payload.get('parts', [])
    if not parts:
        return get_data(payload.get('body', {}))

    plain = ""
    html = ""

    def walk(p_list):
        nonlocal plain, html
        for p in p_list:
            mtype = p.get('mimeType')
            content = get_data(p.get('body', {}))
            
            if mtype == 'text/plain' and not plain:
                plain = content
            elif mtype == 'text/html' and not html:
                html = content
            
            if 'parts' in p:
                walk(p['parts'])

    walk(parts)
    return plain or html or ""

def extract_attachments(service, message_id: str, payload: dict) -> list:
    """
    Recursively extracts attachments from a Gmail message payload.
    Returns a list of dicts: {'filename': str, 'mimeType': str, 'data': bytes}
    """
    import base64
    attachments = []
    
    def walk_parts(parts):
        for part in parts:
            filename = part.get('filename')
            mime_type = part.get('mimeType')
            body = part.get('body', {})
            att_id = body.get('attachmentId')
            
            if filename and att_id:
                try:
                    att = service.users().messages().attachments().get(
                        userId='me', messageId=message_id, id=att_id
                    ).execute()
                    file_data = base64.urlsafe_b64decode(att['data'])
                    attachments.append({
                        'filename': filename,
                        'mimeType': mime_type,
                        'data': file_data
                    })
                except Exception as e:
                    print(f"Failed to download attachment {filename}: {e}")
            
            if 'parts' in part:
                walk_parts(part['parts'])

    walk_parts(payload.get('parts', []))
    return attachments


def fetch_thread_messages(user_id: int, thread_id: str):
    """Fetches full conversation history from Gmail for a thread."""
    service = get_gmail_service(user_id)
    if not service: return []
    
    try:
        thread = service.users().threads().get(userId='me', id=thread_id, format='full').execute()
        messages = []
        for msg in thread.get('messages', []):
            payload = msg.get('payload', {})
            body = extract_message_body(payload)
            
            headers = msg.get('payload', {}).get('headers', [])
            from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown")
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), "")
            
            messages.append({
                'id': msg['id'],
                'from': from_email,
                'subject': subject,
                'date': date,
                'body': body,
                'snippet': msg.get('snippet', '')
            })
        return messages
    except Exception as e:
        print(f"Error fetching thread {thread_id}: {e}")
        return []

def list_gmail_drafts(user_id: int):
    """Fetches all drafts directly from the user's linked Gmail account."""
    service = get_gmail_service(user_id)
    if not service:
        return []
    
    try:
        results = service.users().drafts().list(userId='me').execute()
        drafts_list = results.get('drafts', [])
        
        full_drafts = []
        for d in drafts_list:
            try:
                # Use metadata format to avoid scope restrictions for the list view
                draft = service.users().drafts().get(userId='me', id=d['id'], format='metadata').execute()
                msg = draft.get('message', {})
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])
                
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
                to_email = next((h['value'] for h in headers if h['name'].lower() == 'to'), "No Recipient")
                date = next((h['value'] for h in headers if h['name'].lower() == 'date'), "")
                
                # Fetch full body if possible, otherwise use snippet
                body_content = ""
                try:
                    # Attempt to get full content if needed, but for list we can stick to snippet
                    body_content = msg.get('snippet', '')
                except:
                    pass

                full_drafts.append({
                    'id': d['id'],
                    'message_id': msg.get('id'),
                    'subject': subject,
                    'to': to_email,
                    'date': date,
                    'snippet': msg.get('snippet', ''),
                    'body': body_content
                })
            except Exception as inner_e:
                print(f"Error fetching detail for draft {d['id']}: {inner_e}")
                continue
                
        return full_drafts
    except Exception as e:
        print(f"Error listing Gmail drafts for user {user_id}: {e}")
        return []

def list_gmail_sent(user_id: int):
    """Fetches all sent emails directly from the user's linked Gmail account."""
    service = get_gmail_service(user_id)
    if not service:
        return []
    
    try:
        # Fetch messages with 'SENT' label - using labelIds for maximum robustness
        print(f"DEBUG: Fetching sent messages for user {user_id} using labelIds=['SENT']")
        results = service.users().messages().list(userId='me', labelIds=['SENT']).execute()
        print(f"DEBUG: Raw Results from Google: {results.keys()}")
        messages_list = results.get('messages', [])
        print(f"DEBUG: Found {len(messages_list)} sent messages for user {user_id}")
        
        full_messages = []
        for m in messages_list[:30]: # Limit to last 30 for performance
            try:
                # Use metadata format to ensure headers are available even on restricted scopes
                msg = service.users().messages().get(userId='me', id=m['id'], format='metadata').execute()
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])
                
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
                to_email = next((h['value'] for h in headers if h['name'].lower() == 'to'), "No Recipient")
                date = next((h['value'] for h in headers if h['name'].lower() == 'date'), "")
                
                # For the list view, the snippet is usually enough. 
                # We only fetch full body if explicitly requested or if scope allows.
                full_messages.append({
                    'id': m['id'],
                    'subject': subject,
                    'to': to_email,
                    'date': date,
                    'snippet': msg.get('snippet', ''),
                    'body': msg.get('snippet', '') # Default to snippet for list view
                })
            except Exception as inner_e:
                print(f"Error fetching detail for message {m['id']}: {inner_e}")
                continue
                
        return full_messages
    except Exception as e:
        print(f"Error listing Gmail sent messages for user {user_id}: {e}")
        return []

def get_gmail_message(user_id: int, message_id: str):
    """Fetches the full content of a specific Gmail message."""
    service = get_gmail_service(user_id)
    if not service:
        return None
        
    try:
        # 1. Try FULL format
        try:
            msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            body = extract_message_body(payload)
            
            # If body is still empty, try to get 'raw' data as a nuclear backup
            if not body:
                raw_msg = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
                import base64
                import email
                raw_data = base64.urlsafe_b64decode(raw_msg['raw']).decode('utf-8', errors='replace')
                msg_obj = email.message_from_string(raw_data)
                if msg_obj.is_multipart():
                    for part in msg_obj.walk():
                        if part.get_content_type() == 'text/plain':
                            body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                            break
                else:
                    body = msg_obj.get_payload(decode=True).decode('utf-8', errors='replace')

            return {
                'id': message_id,
                'subject': next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject"),
                'from': next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender"),
                'to': next((h['value'] for h in headers if h['name'].lower() == 'to'), "No Recipient"),
                'date': next((h['value'] for h in headers if h['name'].lower() == 'date'), ""),
                'snippet': msg.get('snippet', ''),
                'body': body if body else msg.get('snippet', ' (Empty Message Body) '),
                'is_restricted': False
            }
        except Exception as full_e:
            print(f"CRITICAL: Full message fetch failed for {message_id}: {full_e}")
            
            # Try to at least get RAW data if FULL failed (sometimes scopes allow raw but not full)
            try:
                raw_msg = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
                import base64
                raw_body = base64.urlsafe_b64decode(raw_msg['raw']).decode('utf-8', errors='replace')
                return {
                    'id': message_id,
                    'subject': "Message (Raw Recovery)",
                    'from': "Unknown",
                    'to': "Unknown",
                    'date': "Recent",
                    'snippet': "Recovered from raw format",
                    'body': raw_body,
                    'is_restricted': False
                }
            except Exception as raw_e:
                # Fallback to metadata
                try:
                    meta = service.users().messages().get(userId='me', id=message_id, format='metadata').execute()
                    headers = meta.get('payload', {}).get('headers', [])
                    return {
                        'id': message_id,
                        'subject': next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject"),
                        'from': next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender"),
                        'to': next((h['value'] for h in headers if h['name'].lower() == 'to'), "No Recipient"),
                        'date': next((h['value'] for h in headers if h['name'].lower() == 'date'), ""),
                        'snippet': meta.get('snippet', ''),
                        'body': f"Technical Error: {str(full_e)} | Raw Backup Error: {str(raw_e)}",
                        'is_restricted': True
                    }
                except:
                    return None
    except Exception as e:
        print(f"Error in get_gmail_message for {message_id}: {e}")
        return None

def update_gmail_draft(user_id: int, draft_id: str, subject: str, body: str):
    """Updates the content of an existing Gmail draft with Markdown-to-HTML support."""
    import base64
    import re
    from email.mime.text import MIMEText
    
    service = get_gmail_service(user_id)
    if not service: return None
    
    try:
        # Convert Markdown to HTML for professional Gmail rendering
        body = body.replace("\r\n", "\n")
        html_body = body
        
        # 1. Bold: **text** -> <strong>text</strong>
        html_body = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_body)
        
        # 2. Italic: _text_ -> <em>text</em>
        html_body = re.sub(r'_(.*?)_', r'<em>\1</em>', html_body)
        
        # 2.5 Links: [text](url) -> <a href="url">text</a>
        html_body = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" target="_blank">\1</a>', html_body)
        
        # 3. Lists: * item -> <li>item</li>
        # Split into paragraphs to handle lists properly
        paragraphs = html_body.split('\n\n')
        processed_paragraphs = []
        for p in paragraphs:
            lines = p.strip().split('\n')
            if all(l.strip().startswith('|') and l.strip().endswith('|') for l in lines if l.strip()):
                table_html = '<table style="width:100%;border-collapse:collapse;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;">'
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    if all(re.match(r'^[-:\s]+$', c) for c in cells):
                        continue
                    tag = 'th' if i == 0 else 'td'
                    th_style = 'padding:10px 14px;border:1px solid #e2e8f0;text-align:left;font-weight:700;color:#1e293b;background:#f1f5f9;font-size:12px;text-transform:uppercase;'
                    td_style = 'padding:8px 14px;border:1px solid #e2e8f0;text-align:left;font-weight:400;color:#334155;'
                    style = th_style if tag == 'th' else td_style
                    row_html = f"<{tag} style='{style}'>" + f"</{tag}><{tag} style='{style}'>".join(cells) + f"</{tag}>"
                    table_html += f"<tr>{row_html}</tr>"
                table_html += '</table>'
                processed_paragraphs.append(table_html)
            elif any(re.match(r'^\s*[\*\-•]\s+', l) for l in lines):
                list_items = []
                for l in lines:
                    match = re.match(r'^\s*[\*\-•]\s+(.*)', l)
                    if match:
                        list_items.append(f"<li>{match.group(1).strip()}</li>")
                    else:
                        if list_items:
                            list_items[-1] = list_items[-1].replace("</li>", f" {l.strip()}</li>")
                processed_paragraphs.append(f"<ul>{''.join(list_items)}</ul>")
            else:
                processed_paragraphs.append(f"<p>{p.replace(chr(10), '<br>')}</p>")
        
        html_body = "".join(processed_paragraphs)
        
        # Create a new message structure
        # Always use HTML if we did any conversion, otherwise fallback
        message = MIMEText(html_body, 'html')
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Update the draft
        updated_draft = service.users().drafts().update(
            userId='me', 
            id=draft_id, 
            body={'message': {'raw': raw}}
        ).execute()
        return updated_draft
    except Exception as e:
        print(f"Error updating Gmail draft {draft_id}: {e}")
        return None

def send_gmail_draft(user_id: int, draft_id: str):
    """Sends an existing Gmail draft."""
    service = get_gmail_service(user_id)
    if not service: return None
    
    try:
        sent_msg = service.users().drafts().send(
            userId='me', 
            body={'id': draft_id}
        ).execute()
        return sent_msg
    except Exception as e:
        print(f"Error sending Gmail draft {draft_id}: {e}")
        return None

def delete_gmail_draft(user_id: int, draft_id: str):
    """Deletes an existing Gmail draft."""
    service = get_gmail_service(user_id)
    if not service: return False
    
    try:
        service.users().drafts().delete(
            userId='me', 
            id=draft_id
        ).execute()
        return True
    except Exception as e:
        print(f"Error deleting Gmail draft {draft_id}: {e}")
        return False

def create_calendar_event(user_id: int, lead_email: str, summary: str, description: str, start_time: datetime.datetime, duration_minutes: int = 30):
    """Creates a Google Calendar event with a Google Meet link."""
    import uuid
    service = get_calendar_service(user_id)
    if not service:
        print(f"Calendar failed: No credentials for user {user_id}")
        return None
        
    end_time = start_time + datetime.timedelta(minutes=duration_minutes)
    
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
        },
        'attendees': [
            {'email': lead_email},
        ],
        'conferenceData': {
            'createRequest': {
                'requestId': str(uuid.uuid4()),
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        },
        'reminders': {
            'useDefault': True,
        },
    }
    
    try:
        created_event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1
        ).execute()
        
        print(f"Google Calendar event created: {created_event.get('htmlLink')}")
        return {
            'event_id': created_event.get('id'),
            'html_link': created_event.get('htmlLink'),
            'meet_link': created_event.get('hangoutLink'),
            'start_time': start_time
        }
    except Exception as e:
        print(f"Error creating calendar event for user {user_id}: {e}")
        return None

def upload_to_drive(user_id: int, filename: str, content: bytes, folder_name: str = "LeadStreamAI_Decks"):
    """Uploads a file to the user's Google Drive and returns a public sharing link."""
    service = get_drive_service(user_id)
    if not service:
        return None
        
    try:
        # 1. Find or Create Folder
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        folders = results.get('files', [])
        
        if not folders:
            folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder.get('id')
        else:
            folder_id = folders[0].get('id')
            
        # 2. Upload File
        from googleapiclient.http import MediaIoBaseUpload
        import io
        
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype='application/pdf', resumable=True)
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        file_id = file.get('id')
        
        # 3. Make file accessible (anyone with the link)
        service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'viewer'}
        ).execute()
        
        # Get the webViewLink
        updated_file = service.files().get(fileId=file_id, fields='webViewLink').execute()
        return updated_file.get('webViewLink')
        
    except Exception as e:
        print(f"Error uploading to Drive for user {user_id}: {e}")
        return None

def renew_all_gmail_watches():
    """Iterate through all linked users and renew their Gmail watch()."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT id FROM users WHERE google_refresh_token IS NOT NULL")
        users = cur.fetchall()
        for user in users:
            try:
                register_gmail_watch(user['id'])
            except Exception as e:
                print(f"Failed to renew watch for user {user['id']}: {e}")
    finally:
        cur.close()
        conn.close()
