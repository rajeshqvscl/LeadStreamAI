from fastapi import APIRouter, Request, HTTPException, Header, Body
from pydantic import BaseModel
from typing import Optional, List
import base64
import json
import os
import psycopg2.extras
from app.database import get_db_connection
from app.services.google_service import (
    get_gmail_service, create_calendar_event, list_gmail_drafts, 
    list_gmail_sent, update_gmail_draft, send_gmail_draft
)
from app.services.llm_services import EmailGenerator
from app.services.email_service import send_email
import datetime
import urllib3
import logging
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# LAST SYNC: 2026-05-01 21:38 (Force Reload)
RAG_TIMEOUT = 300
RAG_URL = "https://rag-sys-gz59.onrender.com"

logger = logging.getLogger(__name__)

def normalize_user_id(user_id: Optional[str]) -> str:
    """Normalizes the user ID from the header to a valid database ID."""
    if not user_id or user_id.strip() == "" or user_id.lower() == "admin":
        return "1"
    
    # If it's already a numeric ID, return it
    if user_id.isdigit():
        return user_id
        
    # If it's a username, email, or full name (like 'sravanthi'), resolve it to an ID
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        # Check username OR email OR full_name
        cur.execute("""
            SELECT id FROM users 
            WHERE LOWER(username) = LOWER(%s) 
            OR LOWER(email) = LOWER(%s)
            OR LOWER(full_name) = LOWER(%s)
        """, (user_id, user_id, user_id))
        res = cur.fetchone()
        cur.close()
        conn.close()
        if res:
            return str(res[0])
    except Exception as e:
        print(f"Error resolving user identity {user_id}: {e}")
        
    return user_id

class AIRefineRequest(BaseModel):
    content: str
    action: str

router = APIRouter()

@router.post("/gmail/pubsub-push")
async def gmail_pubsub_push(request: Request):
    """
    Receives push notifications from Google Cloud Pub/Sub.
    Expects a JSON body with a 'message' field.
    """
    try:
        body = await request.json()
        message = body.get("message", {})
        if not message:
            return {"status": "ok", "detail": "Empty message"}

        # Data is base64 encoded
        data_b64 = message.get("data")
        if not data_b64:
            return {"status": "ok", "detail": "No data in message"}

        data_json = base64.b64decode(data_b64).decode("utf-8")
        data = json.loads(data_json)
        
        email_address = data.get("emailAddress")
        history_id = data.get("historyId")
        
        if not email_address or not history_id:
            return {"status": "ok"}

        print(f"DEBUG: Received Gmail push for {email_address} with historyId {history_id}")
        
        # 1. Find the user associated with this email
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute("SELECT id, last_gmail_history_id FROM users WHERE email = %s", (email_address,))
            user = cur.fetchone()
            if not user:
                print(f"DEBUG: No local user found for {email_address}")
                return {"status": "ok"}
            
            user_id = user['id']
            last_history_id = user['last_gmail_history_id']
            
            # 2. Fetch changes since last history ID
            process_gmail_history(user_id, last_history_id)
            
            # 3. Update last history ID
            cur.execute("UPDATE users SET last_gmail_history_id = %s WHERE id = %s", (history_id, user_id))
            conn.commit()
            
        finally:
            cur.close()
            conn.close()
            
        return {"status": "ok"}
        
    except Exception as e:
        print(f"Error processing Pub/Sub push: {e}")
        # Return 200/ok so Google doesn't keep retrying exponentially if it's a code error
        return {"status": "ok", "error": str(e)}

def process_gmail_history(user_id: int, start_history_id: str):
    """List history changes and identify new messages in tracked threads."""
    from app.services.google_service import get_gmail_service
    service = get_gmail_service(user_id)
    if not service: return

    try:
        # If no previous history ID, we can't fetch diff. We just record the latest and return.
        if not start_history_id:
            return

        history = service.users().history().list(userId='me', startHistoryId=start_history_id, historyTypes=['messageAdded']).execute()
        
        changes = history.get('history', [])
        for change in changes:
            messages_added = change.get('messagesAdded', [])
            for msg_item in messages_added:
                message = msg_item.get('message', {})
                thread_id = message.get('threadId')
                msg_id = message.get('id')
                
                # Check labels - we only care about INBOX (replies)
                full_msg = service.users().messages().get(userId='me', id=msg_id).execute()
                labels = full_msg.get('labelIds', [])
                
                if 'INBOX' in labels and 'SENT' not in labels:
                    # Potential reply! Detect if it matches any of our leads
                    handle_potential_reply(user_id, thread_id, full_msg)

    except Exception as e:
        print(f"Error listing history for user {user_id}: {e}")

def handle_potential_reply(user_id: int, thread_id: str, message_data: dict):
    """Correlates a new Gmail message with a lead and performs AI intent analysis."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # Extract sender email from headers
        headers = message_data.get('payload', {}).get('headers', [])
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
        
        # Clean sender email
        import re
        match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
        sender_email = match.group(0) if match else sender

        # Extract message body
        from app.services.google_service import extract_message_body, extract_attachments, get_gmail_service
        payload = message_data.get('payload', {})
        body = extract_message_body(payload)
        
        # Check for PDF pitch deck attachments
        service = get_gmail_service(user_id)
        msg_id = message_data.get('id')
        attachments = extract_attachments(service, msg_id, payload)
        pdf_attachment = next((att for att in attachments if att['filename'].lower().endswith('.pdf')), None)

        # --- NEW: SELECTIVE ANALYSIS ---
        # Only perform heavy RAG/Intelligence if this email belongs to an existing lead in our outreach pipeline
        conn_check = get_db_connection()
        cur_check = conn_check.cursor()
        cur_check.execute("SELECT id FROM leads_raw WHERE LOWER(email) = LOWER(%s) AND user_id = %s", (sender_email, user_id))
        lead_exists = cur_check.fetchone()
        cur_check.close()
        conn_check.close()
        
        if not lead_exists:
            print(f"DEBUG: Auto-creating new lead for {sender_email}")
            # Extract name from "From" header (e.g. "John Doe <john@site.com>")
            full_name = sender.split('<')[0].strip() if '<' in sender else sender_email.split('@')[0]
            name_parts = full_name.split(' ', 1)
            f_name = name_parts[0]
            l_name = name_parts[1] if len(name_parts) > 1 else ""
            
            conn_new = get_db_connection()
            cur_new = conn_new.cursor()
            cur_new.execute("""
                INSERT INTO leads_raw (email, first_name, last_name, user_id, is_responded, email_status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, FALSE, 'REPLIED', NOW(), NOW())
                RETURNING id
            """, (sender_email, f_name, l_name, user_id))
            conn_new.commit()
            lead_id = cur_new.fetchone()['id']
            cur_new.close()
            conn_new.close()
        else:
            lead_id = lead_exists['id']
            
        # Step 1: AI Intent Classification
        print(f"DEBUG: Classifying reply from {sender_email}...")
        llm = EmailGenerator()
        ai_data = llm.classify_reply(body)
        intent = ai_data.get("intent", "INTERESTED")
        deal_size = ai_data.get("deal_size")
        pitch_deck_url = ai_data.get("pitch_deck_url")
        
        # If we got an actual PDF attachment, upload to Google Drive
        if pdf_attachment:
            from app.services.google_service import upload_to_drive
            # We use the user_id of the person who owns this inbox
            drive_link = upload_to_drive(int(user_id), pdf_attachment['filename'], pdf_attachment['data'])
            if drive_link:
                pitch_deck_url = drive_link
                print(f"DEBUG: Pitch deck uploaded to Drive: {drive_link}")
            else:
                # Fallback to local if drive fails
                import os
                os.makedirs("static/pitch_decks", exist_ok=True)
                safe_filename = "".join(c for c in pdf_attachment['filename'] if c.isalnum() or c in "._-").replace(" ", "_")
                file_path = f"static/pitch_decks/{msg_id}_{safe_filename}"
                with open(file_path, "wb") as f:
                    f.write(pdf_attachment['data'])
                base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                pitch_deck_url = f"{base_url}/{file_path}"
            
        print(f"DEBUG: AI detected intent: {intent}, size: {deal_size}, deck: {pitch_deck_url}")
        
        # --- STRICT RAG ENHANCEMENT (STABLE SESSION) ---
        rag_advice = None
        rag_category = None
        rag_intel = None
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            s = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
            s.mount('https://', HTTPAdapter(max_retries=retries))
            
            # 0. Wake-Up Check
            try:
                s.get(RAG_URL, timeout=10, verify=False)
            except:
                pass

            # 1. RAG Processing (PDF vs Text)
            if pdf_attachment:
                files = {'file': (pdf_attachment['filename'], pdf_attachment['data'])}
                process_res = s.post(f"{RAG_URL}/process", files=files, timeout=300, verify=False)
                if process_res.status_code == 200:
                    rag_data = process_res.json()
                    rag_category = rag_data.get('category') or rag_data.get('type')
                    rag_item_id = rag_data.get('id')
                    
                    if rag_item_id:
                        import time
                        max_polls = 30
                        for poll in range(max_polls):
                            status_res = s.get(f"{RAG_URL}/status/{rag_item_id}", timeout=60, verify=False)
                            if status_res.status_code == 200:
                                status_data = status_res.json()
                                current_status = status_data.get('status', '').lower()
                                if current_status == 'completed' or current_status == 'success':
                                    insights = status_data.get('insights', {})
                                    if insights:
                                        # Capture FULL "A to Z" Data from RAG
                                        rag_advice = f"### RAG VERDICT\n{insights.get('verdict', 'N/A')}\n\n"
                                        rag_advice += f"### SUMMARY\n{insights.get('summary', 'N/A')}\n\n"
                                        
                                        if insights.get('actuals'):
                                            rag_advice += "### ACTUALS & METRICS\n"
                                            for k, v in insights.get('actuals', {}).items():
                                                rag_advice += f"- {k.replace('_', ' ').title()}: {v}\n"
                                            rag_advice += "\n"
                                            
                                        if insights.get('strategy'):
                                            rag_advice += "### STRATEGY RECOMMENDATION\n"
                                            strat = insights.get('strategy', {})
                                            rag_advice += f"- Priority: {strat.get('priority', 'MEDIUM')}\n"
                                            rag_advice += f"- Approach: {strat.get('approach', 'N/A')}\n\n"

                                        rag_category = (insights.get('type') or insights.get('category') or 'INVESTOR').upper()
                                        
                                        rag_intel = {
                                            "answer": rag_advice,
                                            "source": "Pure Llama 3.1 (RAG Engine)",
                                            "category": rag_category,
                                            "sentiment_score": insights.get('score', 80),
                                            "urgency_level": insights.get('strategy', {}).get('priority', 'MEDIUM').upper(),
                                            "strategy": insights.get('strategy', {}),
                                            "actuals": insights.get('actuals', {}),
                                            "signals": insights.get('breakdown', {}),
                                            "key_signals": insights.get('key_signal'),
                                            "verdict": insights.get('verdict'),
                                            "full_insights": insights # STORE EVERYTHING
                                        }
                                        break
                                elif current_status == 'failed':
                                    break
                            time.sleep(10)
            else:
                import io
                files = {'file': ('email_reply.txt', io.StringIO(body).getvalue())}
                s.post(f"{RAG_URL}/ingest", files=files, timeout=60, verify=False)
                # For non-PDF, we use a simpler /ask
                query_msg = f"Based on this email reply from {sender_email}, what should I do next to close this deal? Reply body: {body[:300]}"
                query_res = s.post(f"{RAG_URL}/ask", params={"question": query_msg}, timeout=120, verify=False)
                if query_res.status_code == 200:
                    rag_data = query_res.json()
                    rag_advice = rag_data.get("answer") or rag_data.get("response")
                    rag_intel = rag_data
        except Exception as rag_err:
            print(f"Warning: RAG error: {rag_err}")

        # Step 2: Update Lead Status (Strictly Scoped to User)
        # We only show 'Reverts' that are actually interesting (positive intents)
        positive_intents = ["INTERESTED", "MEETING_REQUESTED", "NEEDS_MORE_INFO"]
        final_status = 'REPLIED'
        # Crucial Fix: Only set is_responded=TRUE for actionable human replies
        should_show_in_intel = intent in positive_intents
        
        if intent == 'NOT_INTERESTED':
            final_status = 'CLOSED'
            
        rag_intel_json = json.dumps(rag_intel) if rag_intel else None

        cur.execute("""
            UPDATE leads_raw 
            SET is_responded = %s, 
                email_status = %s,
                reply_intent = %s,
                deal_size = %s,
                pitch_deck_url = %s,
                rag_advice = %s,
                rag_intelligence = %s,
                sector = COALESCE(%s, sector),
                sentiment_score = %s,
                urgency_level = %s,
                updated_at = NOW(),
                followup_status = 'STOPPED'
            WHERE LOWER(email) = LOWER(%s) AND user_id = %s
            RETURNING id, first_name, last_name, user_id
        """, (should_show_in_intel, final_status, intent, deal_size, pitch_deck_url, rag_advice, rag_intel_json, rag_category, ai_data.get("sentiment_score"), ai_data.get("urgency_level"), sender_email, user_id))

        
        lead = cur.fetchone()
        
        if lead:
            lead_id = lead['id']
            lead_name = f"{lead['first_name'] or ''} {lead['last_name'] or ''}".strip() or "Lead"
            print(f"SUCCESS: Auto-detected reply from {sender_email}. Intent: {intent}")
            conn.commit()

            # Step 3: Auto-Scheduling (Disabled - User will schedule manually)
            if False: # intent in ["INTERESTED", "MEETING_REQUESTED"]:
                # Schedule for 3 days from now at 10 AM UTC
                meeting_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)
                meeting_time = meeting_time.replace(hour=10, minute=0, second=0, microsecond=0)
                
                print(f"DEBUG: Triggering auto-scheduling for {sender_email} at {meeting_time}")
                
                event_data = create_calendar_event(
                    user_id=user_id,
                    lead_email=sender_email,
                    summary=f"Introductory Meeting: LeadStream x {lead_name}",
                    description=f"Automated meeting scheduled based on your interest. \n\nThread: https://mail.google.com/mail/u/0/#inbox/{thread_id}",
                    start_time=meeting_time
                )
                
                if event_data:
                    # Update database with meeting info
                    cur.execute("""
                        UPDATE leads_raw 
                        SET meeting_link = %s,
                            meeting_time = %s 
                        WHERE id = %s
                    """, (event_data['meet_link'], event_data['start_time'], lead_id))
                    conn.commit()
                    
                    # Step 4: Send Confirmation Emails
                    # To Lead
                    lead_confirm_body = f"""
                    Hi {lead['first_name'] or 'there'},
                    
                    Thank you for your interest! I've provisionally scheduled an introductory meeting for us on {meeting_time.strftime('%A, %B %d at %I:%M %p UTC')}.
                    
                    You can join via Google Meet here: {event_data['meet_link']}
                    
                    If this time doesn't work for you, just let me know and we can reschedule.
                    
                    Looking forward to it!
                    """
                    
                    # Get sender details from DB
                    cur.execute("SELECT email, full_name FROM users WHERE id = %s", (user_id,))
                    sender_user = cur.fetchone()
                    
                    send_email(
                        to_email=sender_email,
                        subject=f"Meeting Scheduled: {lead_name} x LeadStream",
                        html_content=lead_confirm_body.replace("\n", "<br>"),
                        from_email=sender_user['email'],
                        from_name=sender_user['full_name'],
                        is_system_email=True
                    )
                    
                    print(f"SUCCESS: Auto-scheduled meeting and sent confirmation to {sender_email}")
            
    except Exception as e:
        print(f"Error handling potential reply for user {user_id}: {e}")
    finally:
        cur.close()
        conn.close()

@router.get("/gmail/inbound-deals")
def get_inbound_deals(
    page: int = 1, 
    per_page: int = 10,
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """Fetches leads who have responded inbound, prioritizing those reached through the site."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    uid = normalize_user_id(user_id)
    offset = (page - 1) * per_page
    
    try:
        # Total Bypass: If a meeting exists, it must show up. Otherwise, show replied leads.
        print(f"DEBUG: Fetching inbound deals for uid: {uid} (Original X-User-Id: {user_id})")
        if user_id == "admin":
            count_query = "SELECT COUNT(*) FROM leads_raw WHERE meeting_time IS NOT NULL OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED'))"
            cur.execute(count_query)
            count_result = cur.fetchone()
            total = count_result['count'] if count_result else 0
            
            query = """
                SELECT * FROM leads_raw 
                WHERE meeting_time IS NOT NULL 
                OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED'))
                ORDER BY updated_at DESC LIMIT %s OFFSET %s
            """
            cur.execute(query, (per_page, offset))
            leads = cur.fetchall()
        else:
            count_query = "SELECT COUNT(*) FROM leads_raw WHERE user_id = %s AND (meeting_time IS NOT NULL OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED')))"
            cur.execute(count_query, (uid,))
            count_result = cur.fetchone()
            total = count_result['count'] if count_result else 0
            
            query = """
                SELECT * FROM leads_raw 
                WHERE user_id = %s 
                AND (meeting_time IS NOT NULL OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED')))
                ORDER BY updated_at DESC LIMIT %s OFFSET %s
            """
            cur.execute(query, (uid, per_page, offset))
            leads = cur.fetchall()
        
        print(f"DEBUG: Found {len(leads)} leads for uid {uid}. Total count in DB: {total}")
        
        return {
            "leads": [dict(l) for l in leads],
            "total": total,
            "page": page,
            "per_page": per_page
        }
    except Exception as e:
        print(f"Error fetching inbound deals: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.post("/gmail/sync-inbound")
def force_sync_inbound(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Manually triggers a scan of the user's Inbox for lead replies."""
    from app.services.google_service import get_gmail_service
    uid = normalize_user_id(user_id)
    service = get_gmail_service(int(uid))
    
    if not service:
        raise HTTPException(status_code=400, detail="Google account not linked")
        
    try:
        # Search Inbox for messages that look like replies or deal-related
        # Queries for: replies (Re:), forwards (Fwd:), or keywords like pitch, deck, interested
        search_query = 'label:INBOX -from:me (subject:Re OR subject:Fwd OR "pitch deck" OR "interested" OR "intro")'
        try:
            results = service.users().messages().list(userId='me', q=search_query, maxResults=50).execute()
        except Exception as q_err:
            if "Metadata scope" in str(q_err):
                logger.error(f"Metadata scope restriction detected for user {uid}")
                raise HTTPException(
                    status_code=403, 
                    detail="Restricted Permissions: Your Gmail connection is currently in 'Metadata-Only' mode. Please Disconnect and Re-connect your Gmail in the Dashboard to grant full search permissions."
                )
            raise q_err
            
        messages = results.get('messages', [])
        found_count = 0
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            for m_meta in messages:
                m_id = m_meta['id']
                
                # PERSISTENT DEDUPLICATION: Skip if already processed in DB
                cur.execute("SELECT 1 FROM gmail_processed_messages WHERE message_id = %s", (m_id,))
                if cur.fetchone():
                    continue
                
                # Full Scan: Always process incoming inbox messages to detect deals
                try:
                    full_msg = service.users().messages().get(userId='me', id=m_id, format='full').execute()
                    handle_potential_reply(int(uid), m_id, full_msg)
                    
                    # Mark as processed in DB
                    cur.execute("INSERT INTO gmail_processed_messages (message_id, user_id) VALUES (%s, %s)", (m_id, int(uid)))
                    conn.commit()
                    found_count += 1
                except Exception as msg_err:
                    print(f"Error processing message {m_id}: {msg_err}")
                    continue
            
            return {"status": "success", "processed": len(messages), "detected": found_count}
        finally:
            cur.close()
            conn.close()
            conn.close()
    except Exception as e:
        print(f"Error in manual sync-inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmail/sync-drafts")
def get_gmail_sync_drafts(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Fetches real-time drafts directly from the user's Gmail account."""
    uid = normalize_user_id(user_id)
    try:
        drafts = list_gmail_drafts(int(uid))
        return drafts
    except Exception as e:
        print(f"Error fetching Gmail sync drafts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmail/sync-sent")
def get_gmail_sync_sent(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Fetches real-time sent messages directly from the user's Gmail account."""
    uid = normalize_user_id(user_id)
    try:
        sent = list_gmail_sent(int(uid))
        return sent
    except Exception as e:
        print(f"Error fetching Gmail sync sent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class UpdateDraftRequest(BaseModel):
    subject: str
    body: str

@router.post("/gmail/update-draft/{draft_id}")
def post_update_gmail_draft(draft_id: str, req: UpdateDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Updates a draft directly on Gmail."""
    uid = normalize_user_id(user_id)
    try:
        res = update_gmail_draft(int(uid), draft_id, req.subject, req.body)
        if not res:
            raise HTTPException(status_code=400, detail="Failed to update draft on Gmail.")
        return {"message": "Draft updated on Gmail successfully"}
    except Exception as e:
        print(f"Error updating Gmail draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/gmail/send-draft/{draft_id}")
def post_send_gmail_draft(draft_id: str, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Sends a draft directly from Gmail."""
    uid = normalize_user_id(user_id)
    try:
        res = send_gmail_draft(int(uid), draft_id)
        if not res:
            raise HTTPException(status_code=400, detail="Failed to send draft from Gmail.")
        return {"message": "Draft sent from Gmail successfully"}
    except Exception as e:
        print(f"Error sending Gmail draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/gmail/ai-refine")
def ai_refine_draft(req: AIRefineRequest):
    """Refines draft content using LLM."""
    try:
        gen = EmailGenerator()
        refined = gen.refine_email(req.content, req.action)
        return {"refined": refined}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmail/meetings")
def get_scheduled_meetings(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Fetches all leads with scheduled meetings for the Calendar view."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    uid = normalize_user_id(user_id)
    
    try:
        if user_id == "admin":
            query = """
                SELECT id, 
                       COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') as lead_name, 
                       email as lead_email, 
                       company_name, meeting_time, meeting_link,
                       linkedin_url, phone, persona
                FROM leads_raw
                WHERE meeting_time IS NOT NULL
                ORDER BY meeting_time ASC
            """
            cur.execute(query)
        else:
            query = """
                SELECT id, 
                       COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') as lead_name, 
                       email as lead_email, 
                       company_name, meeting_time, meeting_link,
                       linkedin_url, phone, persona
                FROM leads_raw
                WHERE user_id = %s AND meeting_time IS NOT NULL
                ORDER BY meeting_time ASC
            """
            cur.execute(query, (uid,))
            
        meetings = []
        for m in cur.fetchall():
            d = dict(m)
            if d.get('meeting_time'):
                # Assuming DB stores UTC, append Z for frontend conversion
                d['meeting_time'] = d['meeting_time'].isoformat() + "Z"
            meetings.append(d)
        return meetings
    except Exception as e:
        print(f"Error fetching meetings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.post("/gmail/schedule-meeting/{lead_id}")
def schedule_manual_meeting(lead_id: int, data: dict = Body(...), user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Manually triggers a calendar event creation for a specific lead with a chosen time."""
    from app.services.google_service import create_calendar_event
    from app.services.email_service import send_email
    import datetime
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    uid = normalize_user_id(user_id)
    
    # Extract custom time from body if provided
    custom_time_str = data.get('meeting_time')
    
    try:
        # Fetch lead details
        cur.execute("SELECT id, first_name, last_name, email FROM leads_raw WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
            
        if custom_time_str:
            meeting_time = datetime.datetime.fromisoformat(custom_time_str.replace('Z', '+00:00'))
        else:
            # Fallback: Schedule for 2 days from now at 2 PM UTC
            meeting_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
            meeting_time = meeting_time.replace(hour=14, minute=0, second=0, microsecond=0)
        
        lead_name = f"{lead['first_name'] or ''} {lead['last_name'] or ''}".strip() or "Lead"
        
        event_data = create_calendar_event(
            user_id=uid,
            lead_email=lead['email'],
            summary=f"Strategy Session: {lead_name} x LeadStream",
            description=f"Introductory call to discuss personalized solutions. \n\nLead: {lead['email']}",
            start_time=meeting_time
        )
        
        if not event_data:
            raise HTTPException(status_code=500, detail="Failed to create Google Calendar event")
            
        # Update database
        cur.execute("""
            UPDATE leads_raw 
            SET meeting_link = %s,
                meeting_time = %s 
            WHERE id = %s
        """, (event_data['meet_link'], event_data['start_time'], lead_id))
        conn.commit()
        
        # Send confirmation email
        cur.execute("SELECT email, full_name FROM users WHERE id = %s", (uid,))
        sender_user = cur.fetchone()
        
        confirm_body = f"Hi {lead['first_name'] or 'there'},\n\nI've scheduled our strategy session for {meeting_time.strftime('%A, %B %d at %I:%M %p UTC')}.\n\nYou can join via Google Meet here: {event_data['meet_link']}\n\nLooking forward to it!"
        
        # Final Dispatch: Prefer Gmail API for personalized scheduling
        success = send_email(
            to_email=lead['email'],
            subject=f"Meeting Scheduled: {lead_name} x LeadStream",
            html_content=confirm_body.replace("\n", "<br>"),
            from_email=sender_user['email'],
            from_name=sender_user['full_name'],
            is_system_email=False,
            user_id=uid
        )
        
        return {"status": "success", "event": event_data, "email_sent": success}
        
    except Exception as e:
        print(f"Error manual scheduling: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

class RescheduleRequest(BaseModel):
    new_time: str

class BulkMeetingActionRequest(BaseModel):
    lead_ids: List[int]

@router.post("/gmail/reschedule/{lead_id}")
def reschedule_meeting(lead_id: int, payload: RescheduleRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Updates the meeting time for an existing scheduled meeting."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    uid = normalize_user_id(user_id)
    
    try:
        if user_id == "admin":
            cur.execute("UPDATE leads_raw SET meeting_time = %s WHERE id = %s RETURNING id, first_name, email, meeting_link", (payload.new_time, lead_id))
        else:
            cur.execute("UPDATE leads_raw SET meeting_time = %s WHERE id = %s AND user_id = %s RETURNING id, first_name, email, meeting_link", (payload.new_time, lead_id, uid))
            
        updated_lead = cur.fetchone()
        if not updated_lead:
            raise HTTPException(status_code=404, detail="Meeting not found or unauthorized")
            
        conn.commit()

        # Send confirmation email
        cur.execute("SELECT email, full_name FROM users WHERE id = %s", (uid,))
        sender_user = cur.fetchone()
        sender_email = sender_user['email'] if sender_user else None

        if sender_email:
            try:
                meeting_dt = datetime.datetime.fromisoformat(payload.new_time.replace('Z', '+00:00'))
                formatted_time = meeting_dt.strftime('%A, %B %d at %I:%M %p')
            except Exception:
                formatted_time = payload.new_time

            reschedule_body = f"""
### Strategy Session Updated

Hi {updated_lead['first_name'] or 'there'},

I have successfully adjusted our upcoming strategy session on my end. Our new confirmed temporal slot is:

**{formatted_time} (IST)**

You should receive an updated calendar invitation with the meeting link shortly. For your convenience, the meeting coordinates are also listed below:

**Meeting Link:** {updated_lead['meeting_link'] or 'Pending Confirmation'}

In the meantime, I have attached our latest **Company Profile** and **Executive Summary** to this email. I recommend reviewing these before our session to ensure we can make the most of our time together.

Looking forward to our conversation.

Best regards,

**{sender_user['full_name'] if sender_user else 'LeadStream Team'}**  
LeadStream Strategy Division
            """

            send_email(
                to_email=updated_lead['email'],
                subject=f"Confirmed: Rescheduled Strategy Session - {updated_lead['first_name'] or ''}",
                html_content=reschedule_body,
                from_email=sender_email,
                from_name=sender_user['full_name'] if sender_user else "LeadStream Team",
                is_system_email=False,
                user_id=uid
            )

        return {"success": True, "message": "Meeting successfully rescheduled"}
    except Exception as e:
        print(f"Error rescheduling: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.post("/gmail/meetings/bulk-cancel")
def bulk_cancel_meetings(req: BulkMeetingActionRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Clears meeting time and link for multiple leads."""
    conn = get_db_connection()
    cur = conn.cursor()
    uid = normalize_user_id(user_id)
    
    try:
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        if user_id == "admin":
            query = f"UPDATE leads_raw SET meeting_time = NULL, meeting_link = NULL WHERE id IN ({format_strings})"
            cur.execute(query, tuple(req.lead_ids))
        else:
            query = f"UPDATE leads_raw SET meeting_time = NULL, meeting_link = NULL WHERE id IN ({format_strings}) AND user_id = %s"
            cur.execute(query, (*req.lead_ids, uid))
            
        conn.commit()
        return {"success": True, "message": f"Successfully cancelled {cur.rowcount} meetings"}
    except Exception as e:
        print(f"Error bulk cancelling: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

# Global cache to prevent redundant API calls
INBOX_CACHE = {}
CACHE_EXPIRY = 30 # seconds

@router.get("/gmail/inbox")
def get_unified_inbox(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Fetches a list of the latest replies/messages with 30s caching for speed."""
    from app.services.google_service import get_gmail_service
    uid = normalize_user_id(user_id)
    
    # Check Cache
    now = datetime.datetime.now()
    if uid in INBOX_CACHE:
        cache_data, timestamp = INBOX_CACHE[uid]
        if (now - timestamp).seconds < CACHE_EXPIRY:
            return {"messages": cache_data, "cached": True, "connected": True}

    service = get_gmail_service(int(uid))
    if not service:
        return {"messages": [], "connected": False}
    
    try:
        # Attempt to search for latest 25 INCOMING messages
        try:
            results = service.users().messages().list(userId='me', q='label:INBOX -from:me', maxResults=25).execute()
        except Exception as list_err:
            if "Metadata scope does not support 'q' parameter" in str(list_err):
                print(f"DEBUG: Restricted scope for user {uid}. Falling back to simple list.")
                # Fallback to simple list without 'q' filter if scope is restricted
                results = service.users().messages().list(userId='me', maxResults=25).execute()
            else:
                raise list_err
        
        messages_meta = results.get('messages', [])
        
        full_messages = []
        for meta in messages_meta:
            # Switch to 'metadata' format to get headers even on restricted tokens
            msg = service.users().messages().get(userId='me', id=meta['id'], format='metadata').execute()
            
            headers = msg.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown")
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), "")
            
            # Clean Snippet: Strip "Subject:" from the start of the snippet if Gmail included it
            raw_snippet = msg.get('snippet', '')
            clean_snippet = raw_snippet
            if raw_snippet.lower().startswith("subject:"):
                # Try to skip the subject line part of the snippet
                # Snippets often look like "Subject: Text... Actual Body Text"
                # We'll try to find where the subject might end (looking for common body starts or just skipping the length)
                # For safety, we'll just remove the "Subject:" prefix and let it be
                clean_snippet = raw_snippet.replace("Subject: ", "", 1).replace("subject: ", "", 1)
            
            full_messages.append({
                'id': msg['id'],
                'threadId': msg['threadId'],
                'from': sender,
                'subject': subject,
                'date': date,
                'snippet': clean_snippet,
                'is_read': 'UNREAD' not in msg.get('labelIds', [])
            })
        
        # Update Cache
        INBOX_CACHE[uid] = (full_messages, now)
        return {"messages": full_messages, "connected": True}
    except Exception as e:
        print(f"Error fetching inbox for user {user_id}: {e}")
        return {"messages": [], "error": str(e), "connected": True}

@router.get("/gmail/message/{message_id}")
def get_message_detail(message_id: str, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Fetches full details including body for a specific Gmail message."""
    from app.services.google_service import get_gmail_message
    uid = normalize_user_id(user_id)
    
    try:
        msg = get_gmail_message(int(uid), message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        return msg
    except Exception as e:
        print(f"Error in get_message_detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def poll_all_users_for_replies():
    """Manually iterate through active users and check for lead replies."""
    from app.services.google_service import get_gmail_service
    from app.database import get_db_connection
    import psycopg2.extras
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Find all users with Google credentials
        cur.execute("SELECT id FROM users WHERE google_refresh_token IS NOT NULL")
        users = cur.fetchall()
        
        for user in users:
            uid = user['id']
            service = get_gmail_service(uid)
            if not service: continue
            
            # Check for latest 50 messages for comprehensive reply detection
            try:
                # Exclude messages sent by the user to focus on incoming replies
                results = service.users().messages().list(userId='me', q='label:INBOX -from:me', maxResults=50).execute()
                for msg_meta in results.get('messages', []):
                    # Check if this thread/message is from a lead
                    msg = service.users().messages().get(userId='me', id=msg_meta['id'], format='metadata').execute()
                    
                    # Skip if the message is sent BY the user
                    labels = msg.get('labelIds', [])
                    if 'SENT' in labels:
                        continue
                        
                    headers = msg.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
                    
                    # Extract pure email from "Name <email@site.com>"
                    import re
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
                    if email_match:
                        sender_email = email_match.group(0).lower()
                        
                        # Check if this email exists as a lead (regardless of owner) and hasn't responded yet
                        cur.execute("""
                            SELECT id, user_id FROM leads_raw 
                            WHERE LOWER(email) = LOWER(%s) AND is_responded = FALSE
                            LIMIT 1
                        """, (sender_email,))
                        
                        found_lead = cur.fetchone()
                        if found_lead:
                            target_uid = found_lead['user_id'] or uid
                            print(f"POLLING: Found pending reply from {sender_email} (Lead ID: {found_lead['id']}). Processing for owner {target_uid}...")
                            
                            # Fetch full message data for classification
                            try:
                                full_msg_data = service.users().messages().get(userId='me', id=msg_meta['id'], format='full').execute()
                                handle_potential_reply(target_uid, full_msg_data.get('threadId'), full_msg_data)
                                conn.commit()
                            except Exception as fetch_err:
                                print(f"Error fetching full message for polling: {fetch_err}")
            except Exception as e:
                print(f"Error polling for user {uid}: {e}")
                
    except Exception as e:
        print(f"Global polling error: {e}")
    finally:
        cur.close()
        conn.close()

@router.post("/gmail/retro-sync-pdfs")
def retro_sync_pdfs(request: Request, x_user_id: Optional[str] = Header(None)):
    user_id = normalize_user_id(x_user_id)
    
    try:
        service = get_gmail_service(int(user_id))
        if not service:
            return {"success": False, "error": "Gmail service not initialized for this user"}
            
        # Scan Gmail for PDFs (all messages, not just Inbox)
        results = service.users().messages().list(userId='me', q='has:attachment filename:pdf', maxResults=50).execute()
        messages = results.get('messages', [])
        
        count = 0
        rag_url = "https://rag-sys-gz59.onrender.com"
        from app.services.google_service import extract_attachments
        
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
            
            import re
            match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
            sender_email = match.group(0) if match else sender
            
            payload = msg_data.get('payload', {})
            attachments = extract_attachments(service, msg['id'], payload)
            pdf_attachment = next((att for att in attachments if att['filename'].lower().endswith('.pdf')), None)
            
            if pdf_attachment:
                import os
                import requests
                os.makedirs("static/pitch_decks", exist_ok=True)
                safe_filename = "".join(c for c in pdf_attachment['filename'] if c.isalnum() or c in "._-").replace(" ", "_")
                file_path = f"static/pitch_decks/{msg['id']}_{safe_filename}"
                with open(file_path, "wb") as f:
                    f.write(pdf_attachment['data'])
                
                # Use dynamic backend URL instead of localhost
                base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                pitch_deck_url = f"{base_url}/{file_path}"
                
                # --- STRICT RAG ONLY (STABLE SESSION) ---
                rag_category = None
                rag_advice = None
                rag_intel = None
                try:
                    import requests
                    from requests.adapters import HTTPAdapter
                    from urllib3.util.retry import Retry
                    
                    s = requests.Session()
                    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
                    s.mount('https://', HTTPAdapter(max_retries=retries))
                    
                    # 0. Wake-Up Check (No verify for speed/stability)
                    try:
                        s.get(RAG_URL, timeout=10, verify=False)
                    except:
                        pass

                    files = {'file': (pdf_attachment['filename'], pdf_attachment['data'])}
                    process_res = s.post(f"{RAG_URL}/process", files=files, timeout=300, verify=False)
                    
                    if process_res.status_code == 200:
                        rag_data = process_res.json()
                        rag_category = rag_data.get('category') or rag_data.get('type')
                        rag_item_id = rag_data.get('id')
                        
                        if rag_item_id:
                            import time
                            max_polls = 30
                            for poll in range(max_polls):
                                status_res = s.get(f"{RAG_URL}/status/{rag_item_id}", timeout=60, verify=False)
                                if status_res.status_code == 200:
                                    status_data = status_res.json()
                                    current_status = status_data.get('status', '').lower()
                                    if current_status == 'completed' or current_status == 'success':
                                        insights = status_data.get('insights', {})
                                        if insights:
                                            # Capture RAW RAG OUTPUT as the primary advice
                                            rag_advice = insights.get('summary') or insights.get('verdict') or "Analysis completed but no summary provided."
                                            
                                            rag_category = (insights.get('type') or insights.get('category') or 'INVESTOR').upper()
                                            
                                            rag_intel = {
                                                "answer": rag_advice,
                                                "source": "Pure Llama 3.1 (RAG Engine)",
                                                "category": rag_category,
                                                "sentiment_score": insights.get('score', 80),
                                                "urgency_level": insights.get('strategy', {}).get('priority', 'MEDIUM').upper(),
                                                "strategy": insights.get('strategy', {}),
                                                "actuals": insights.get('actuals', {}),
                                                "signals": insights.get('breakdown', {}),
                                                "key_signals": insights.get('key_signal'),
                                                "verdict": insights.get('verdict'),
                                                "full_insights": insights
                                            }
                                            break
                                    elif current_status == 'failed':
                                        break
                                time.sleep(10)
                except Exception as re_err:
                    print(f"RAG Retro Error: {re_err}")

                import json
                rag_intel_json = json.dumps(rag_intel) if rag_intel else None

                # Update database
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                
                # Fetch lead data first for draft generation
                cur.execute("SELECT * FROM leads_raw WHERE LOWER(email) = LOWER(%s)", (sender_email,))
                lead_row = cur.fetchone()
                
                fresh_draft_body = None
                if lead_row and rag_advice:
                    try:
                        from app.services.llm_services import EmailGenerator
                        generator = EmailGenerator()
                        lead_data_for_draft = {**dict(lead_row), "rag_advice": rag_advice}
                        fresh_draft = generator.generate_email(lead_data_for_draft)
                        if fresh_draft:
                            fresh_draft_body = fresh_draft.get('body')
                            if rag_intel: rag_intel["draft"] = fresh_draft_body
                    except Exception as draft_err:
                        print(f"Failed to generate retro draft: {draft_err}")

                cur.execute("""
                    UPDATE leads_raw 
                    SET pitch_deck_url = %s,
                        sector = COALESCE(%s, sector),
                        rag_advice = %s,
                        rag_intelligence = %s,
                        email_draft = COALESCE(%s, email_draft)
                    WHERE LOWER(email) = LOWER(%s) 
                    AND (pitch_deck_url IS NULL OR pitch_deck_url = '' OR pitch_deck_url LIKE 'Attached PDF:%%' OR rag_advice IS NULL)
                """, (pitch_deck_url, rag_category, rag_advice, json.dumps(rag_intel) if rag_intel else None, fresh_draft_body, sender_email))
                
                if cur.rowcount > 0:
                    conn.commit()
                    count += 1
                cur.close()
                conn.close()
                
        return {"success": True, "updated_deals": count, "message": f"Retro-sync complete. {count} pitch decks processed and classified."}
    except Exception as e:
        print(f"Retro sync error: {e}")
        return {"success": False, "error": str(e)}
