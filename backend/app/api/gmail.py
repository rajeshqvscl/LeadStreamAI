from fastapi import APIRouter, Request, HTTPException, Header, Body
from pydantic import BaseModel
from typing import Optional
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
import logging

logger = logging.getLogger(__name__)

def normalize_user_id(user_id: Optional[str]) -> str:
    """Normalizes the user ID from the header to a valid database ID."""
    if not user_id or user_id.strip() == "" or user_id.lower() == "admin":
        return "1"
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

        # Step 1: AI Intent Classification
        print(f"DEBUG: Classifying reply from {sender_email}...")
        llm = EmailGenerator()
        ai_data = llm.classify_reply(body)
        intent = ai_data.get("intent", "INTERESTED")
        deal_size = ai_data.get("deal_size")
        pitch_deck_url = ai_data.get("pitch_deck_url")
        
        # If we got an actual PDF attachment, override pitch_deck_url to point to the local static server
        if pdf_attachment:
            import os
            os.makedirs("static/pitch_decks", exist_ok=True)
            safe_filename = "".join(c for c in pdf_attachment['filename'] if c.isalnum() or c in "._-").replace(" ", "_")
            file_path = f"static/pitch_decks/{msg_id}_{safe_filename}"
            with open(file_path, "wb") as f:
                f.write(pdf_attachment['data'])
            
            # Use dynamic backend URL instead of localhost
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            pitch_deck_url = f"{base_url}/{file_path}"
            
        print(f"DEBUG: AI detected intent: {intent}, size: {deal_size}, deck: {pitch_deck_url}")
        
        # Step 1b: RAG Intelligence Enhancement (New)
        rag_advice = None
        try:
            import requests
            import io
            rag_url = "https://rag-sys-gz59.onrender.com"
            
            # 1. Ingest into RAG memory (Prioritize PDF Pitch Deck if exists)
            if pdf_attachment:
                files = {'file': (pdf_attachment['filename'], pdf_attachment['data'])}
                requests.post(f"{rag_url}/ingest", files=files, timeout=120)
                query_msg = f"The lead ({sender_email}) attached a pitch deck. Based on their email: '{body[:200]}', analyze the attached deck and summarize the key takeaways, value proposition, and your advice on next steps."
            else:
                files = {'file': ('email_reply.txt', io.StringIO(body).getvalue())}
                requests.post(f"{rag_url}/ingest", files=files, timeout=120)
                if pitch_deck_url:
                    query_msg = f"The lead ({sender_email}) sent a pitch deck URL ({pitch_deck_url}). Based on their email: '{body[:300]}', analyze the deal and summarize the key takeaways, value proposition, and your advice on next steps."
                else:
                    query_msg = f"Based on this email reply from {sender_email}, what should I do next to close this deal? Reply body: {body[:300]}"
                
            # 2. Query RAG for deep advice
                
            query_res = requests.get(f"{rag_url}/query", params={"q": query_msg}, timeout=120)
            if query_res.status_code == 200:
                rag_data = query_res.json()
                rag_advice = rag_data.get("answer") or rag_data.get("response") or str(rag_data)
        except Exception as rag_err:
            print(f"Warning: RAG error: {rag_err}")

        # Step 2: Update Lead Status (Global Search)
        # If not interested, we close the lead automatically.
        final_status = 'REPLIED'
        if intent == 'NOT_INTERESTED':
            final_status = 'CLOSED'
            
        cur.execute("""
            UPDATE leads_raw 
            SET is_responded = TRUE, 
                email_status = %s,
                reply_intent = %s,
                deal_size = %s,
                pitch_deck_url = %s,
                rag_advice = %s,
                sentiment_score = %s,
                urgency_level = %s,
                updated_at = NOW(),
                followup_status = 'STOPPED'
            WHERE LOWER(email) = LOWER(%s)
            RETURNING id, first_name, last_name, user_id
        """, (final_status, intent, deal_size, pitch_deck_url, rag_advice, ai_data.get("sentiment_score"), ai_data.get("urgency_level"), sender_email))

        
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
def get_inbound_deals(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Fetches leads who have actually responded inbound (is_responded = TRUE) for the Inbound Deals dashboard."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    uid = normalize_user_id(user_id)
    
    try:
        if user_id == "admin":
            query = """
                SELECT id, first_name, last_name, email, company_name, sector,
                       reply_intent, deal_size, pitch_deck_url, rag_advice, updated_at,
                       meeting_time, meeting_link, is_responded, linkedin_url,
                       sentiment_score, urgency_level
                FROM leads_raw
                WHERE is_responded = TRUE
                ORDER BY updated_at DESC
            """
            cur.execute(query)
        else:
            query = """
                SELECT id, first_name, last_name, email, company_name, sector,
                       reply_intent, deal_size, pitch_deck_url, rag_advice, updated_at,
                       meeting_time, meeting_link, is_responded, linkedin_url,
                       sentiment_score, urgency_level
                FROM leads_raw
                WHERE user_id = %s AND is_responded = TRUE
                ORDER BY updated_at DESC
            """
            cur.execute(query, (uid,))

            
        leads = cur.fetchall()
        return [dict(l) for l in leads]
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
        # Search Inbox for messages not from me
        try:
            results = service.users().messages().list(userId='me', q='label:INBOX -from:me', maxResults=50).execute()
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
                msg = service.users().messages().get(userId='me', id=m_meta['id'], format='metadata').execute()
                headers = msg.get('payload', {}).get('headers', [])
                sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
                
                import re
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
                if email_match:
                    sender_email = email_match.group(0).lower()
                    
                    cur.execute("SELECT id FROM leads_raw WHERE LOWER(email) = LOWER(%s) AND is_responded = FALSE LIMIT 1", (sender_email,))
                    lead = cur.fetchone()
                    if lead:
                        # Fetch full content for AI classification
                        full_msg = service.users().messages().get(userId='me', id=m_meta['id'], format='full').execute()
                        handle_potential_reply(int(uid), full_msg.get('threadId'), full_msg)
                        conn.commit()
                        found_count += 1
            
            return {"status": "success", "processed": len(messages), "detected": found_count}
        finally:
            cur.close()
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
                formatted_time = meeting_dt.strftime('%b %d, %Y at %H:%M')
            except ValueError:
                formatted_time = payload.new_time

            send_email(
                to_email=updated_lead['email'],
                subject=f"Meeting Rescheduled - LeadStream",
                html_content=f"Hi {updated_lead['first_name'] or ''},\n\nYour strategy session has been successfully rescheduled to {formatted_time}.\n\nMeeting Link: {updated_lead['meeting_link'] or 'Pending'}\n\nLooking forward to speaking with you!\n\nBest,\nLeadStream Team",
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
        # Search for latest 25 INCOMING messages (label:INBOX and not from the user)
        # This prevents sent messages and self-correspondence from cluttering the view
        results = service.users().messages().list(userId='me', q='label:INBOX -from:me', maxResults=25).execute()
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

@router.post("/retro-sync-pdfs")
def retro_sync_pdfs(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        service = get_gmail_service(user_id)
        results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=50).execute()
        messages = results.get('messages', [])
        
        count = 0
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
                os.makedirs("static/pitch_decks", exist_ok=True)
                safe_filename = "".join(c for c in pdf_attachment['filename'] if c.isalnum() or c in "._-").replace(" ", "_")
                file_path = f"static/pitch_decks/{msg['id']}_{safe_filename}"
                with open(file_path, "wb") as f:
                    f.write(pdf_attachment['data'])
                
                # Use dynamic backend URL instead of localhost
                base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                pitch_deck_url = f"{base_url}/{file_path}"
                
                # Update database
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE leads_raw SET pitch_deck_url = %s WHERE email = %s AND (pitch_deck_url IS NULL OR pitch_deck_url = '' OR pitch_deck_url LIKE 'Attached PDF:%%')",
                    (pitch_deck_url, sender_email)
                )
                if cur.rowcount > 0:
                    conn.commit()
                    count += 1
                cur.close()
                conn.close()
                
        return {"success": True, "updated_deals": count}
    except Exception as e:
        print(f"Retro sync error: {e}")
        return {"success": False, "error": str(e)}
