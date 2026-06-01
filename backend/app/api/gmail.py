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
from app.api.drafts import markdown_to_html
import datetime
import urllib3
import logging
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        return super().default(obj)

# LAST SYNC: 2026-05-01 21:38 (Force Reload)
RAG_TIMEOUT = 300
RAG_URL = "https://rag-sys-gz59.onrender.com"

logger = logging.getLogger(__name__)

# --- REDIS CACHE INITIALIZATION ---
redis_client = None
redis_available = False

try:
    import redis
    REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
    redis_client = redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )
    redis_client.ping()
    redis_available = True
    logger.info(f"SUCCESS: Connected to Redis Cache at {REDIS_URL.split('@')[-1]}")
except Exception as re_err:
    logger.warning(f"NOTICE: Redis is not active. Falling back to direct database execution. Error: {re_err}")
    redis_client = None
    redis_available = False

def invalidate_inbound_deals_cache(user_id: str):
    if redis_available and redis_client:
        try:
            pattern = f"inbound_deals:{user_id}:*"
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
                logger.info(f"SUCCESS: Invalidated cache keys for pattern: {pattern}")
        except Exception as ie:
            logger.error(f"Failed to invalidate Redis cache: {ie}")

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
        # Extract message body and STRIP quoted history to avoid analyzing our own sent text/PDFs
        from app.services.google_service import extract_message_body, extract_attachments, get_gmail_service
        payload = message_data.get('payload', {})
        full_body = extract_message_body(payload)
        
        # Strip everything after 'On ... wrote:', 'On ... at ...:', 'From: ...', etc.
        # Handles case where email clients join inline like "iPhoneOn 8 May 2026, at 10:50 AM"
        pattern = r'(?mi)(?:On\s+.*wrote:|\bOn\s+.*\b(?:at\b)?\s*\d{1,2}:\d{2}.*?:|On\s+\d{1,2}\s+[a-z]+\s+\d{4},?\s+at\s+\d{1,2}:\d{2}|On\s+[a-z]+,?\s+[a-z]+\s+\d{1,2},?\s+\d{4}|\bFrom:\s+.*@.*|^---+\s*Original\s+Message\s*---+|----------\s*Forwarded\s+message\s*----------)'
        parts = re.split(pattern, full_body)
        body = parts[0].strip() if parts else full_body.strip()
        
        # 0. SENDER CHECK: Abort if this message was actually sent by the user (sent folder bleed-over)
        cur_user = conn.cursor()
        cur_user.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        user_record = cur_user.fetchone()
        cur_user.close()
        
        if user_record and user_record[0].lower() in sender_email.lower():
            print(f"DEBUG: Skipping {sender_email} — this is a sent message, not a reply.")
            return

        # Check for PDF pitch deck attachments
        service = get_gmail_service(user_id)
        msg_id = message_data.get('id')
        attachments = extract_attachments(service, msg_id, payload)
        pdf_attachment = next((att for att in attachments if att['filename'].lower().endswith('.pdf')), None)

        # --- STRICT OUTREACH-ONLY FILTER ---
        # ONLY process replies from leads we actually emailed through this platform.
        # Skip all random inbox emails (marketing, newsletters, unknown senders, etc.)
        conn_check = get_db_connection()
        cur_check = conn_check.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur_check.execute(
            "SELECT id FROM leads_raw WHERE LOWER(email) = LOWER(%s) AND user_id = %s AND email_status IN ('SENT', 'REPLIED', 'CLOSED', 'SCHEDULED')",
            (sender_email, user_id)
        )
        lead_exists = cur_check.fetchone()
        cur_check.close()
        conn_check.close()
        
        if not lead_exists:
            print(f"DEBUG: Skipping {sender_email} — not a lead we contacted through this platform.")
            return  # Hard stop — don't process random inbox mail
        
        lead_id = lead_exists['id']
        # Step 1: AI Intent Classification
        print(f"DEBUG: Classifying reply from {sender_email}...")
        from app.services.llm_services import EmailGenerator
        llm = EmailGenerator()
        ai_data = llm.classify_reply(body)
        intent = ai_data.get("intent", "INTERESTED")
        
        # USER REQUEST: Do not use email-body estimation for the primary revenue field.
        # Only show financial metrics if they are verified in a PDF.
        deal_size = None 
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
            
        print(f"DEBUG: AI detected intent: {intent}, body_size_estimation: {ai_data.get('deal_size')}, deck: {pitch_deck_url}")
        
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
                s.get(RAG_URL, timeout=60, verify=False)
            except:
                pass

            # 1. RAG Processing (PDF vs Text)
            if pdf_attachment:
                files = {'file': (pdf_attachment['filename'], pdf_attachment['data'])}
                process_res = s.post(f"{RAG_URL}/process", files=files, timeout=300, verify=False)
                if process_res.status_code == 200:
                    rag_data = process_res.json()
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
                                        
                                        # USER REQUEST: Populate deal_size ONLY from PDF insights
                                        if insights.get('actuals'):
                                            actuals = insights.get('actuals', {})
                                            deal_size = actuals.get('revenue') or actuals.get('deal_size')
                                            
                                            rag_advice += "### ACTUALS & METRICS\n"
                                            for k, v in actuals.items():
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
                                            "category": rag_category,
                                            "actuals": insights.get('actuals', {}),
                                            "strategy": insights.get('strategy', {}),
                                            "full_insights": insights,
                                            "filename": pdf_attachment['filename']
                                        }
                                        break
                                time.sleep(10)
            else:
                # Non-PDF replies get generic advice, but deal_size remains None
                import io
                files = {'file': ('email_reply.txt', io.StringIO(body).getvalue())}
                s.post(f"{RAG_URL}/ingest", files=files, timeout=60, verify=False)
                query_msg = f"Reply body: {body[:300]}"
                query_res = s.post(f"{RAG_URL}/ask", params={"question": query_msg}, timeout=120, verify=False)
                if query_res.status_code == 200:
                    rag_data = query_res.json()
                    rag_advice = rag_data.get("answer") or rag_data.get("response")
                    rag_intel = rag_data
        except Exception as rag_err:
            print(f"Warning: RAG error: {rag_err}")
 
        # Step 2: Update Lead Status
        all_intents = ["INTERESTED", "MEETING_REQUESTED", "NEEDS_MORE_INFO", "NOT_INTERESTED"]
        final_status = 'REPLIED'
        should_show_in_intel = intent in all_intents
        if intent == 'NOT_INTERESTED':
            final_status = 'CLOSED'
            
        # EXTRA SAFEGUARD: Never set deal_size from LLM hallucination.
        # Only keep it if it came from actual PDF analysis.
        if not pdf_attachment:
            deal_size = None

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
                remarks = %s,
                updated_at = NOW(),
                followup_status = 'STOPPED'
            WHERE LOWER(email) = LOWER(%s) AND user_id = %s
            RETURNING id, first_name, last_name, user_id
        """, (should_show_in_intel, final_status, intent, deal_size, pitch_deck_url, rag_advice, rag_intel_json, rag_category, ai_data.get("sentiment_score"), ai_data.get("urgency_level"), body, sender_email, user_id))

        
        lead = cur.fetchone()
        
        if lead:
            lead_id = lead['id']
            lead_name = f"{lead['first_name'] or ''} {lead['last_name'] or ''}".strip() or "Lead"
            print(f"SUCCESS: Auto-detected reply from {sender_email}. Intent: {intent}")
            conn.commit()
            invalidate_inbound_deals_cache(str(user_id))

            # Stop followups for ALL other leads from the same company
            try:
                cur.execute("SELECT company_name FROM leads_raw WHERE id = %s", (lead_id,))
                company_row = cur.fetchone()
                if company_row:
                    company_name = company_row['company_name'] if isinstance(company_row, dict) else company_row[0]
                    if company_name and company_name.strip() and company_name.strip().upper() not in ('', 'INDEPENDENT', 'N/A', 'NONE', '-'):
                        cur.execute("""
                            SELECT id, first_name, last_name, email FROM leads_raw
                            WHERE company_name ILIKE %s AND id != %s
                            AND followup_status = 'ACTIVE' AND is_responded = FALSE
                        """, (company_name, lead_id))
                        same_company_leads = cur.fetchall()
                        for sc_lead in same_company_leads:
                            sc_id = sc_lead['id']
                            sc_name = f"{sc_lead['first_name'] or ''} {sc_lead['last_name'] or ''}".strip() or sc_lead['email']
                            cur.execute("""
                                UPDATE leads_raw SET followup_status = 'STOPPED', updated_at = NOW()
                                WHERE id = %s
                            """, (sc_id,))
                            from app.models.lead import add_activity_log
                            add_activity_log(sc_id, 'FOLLOWUP_STOPPED', f'Reply received from {lead_name} ({sender_email}) at same company — auto-stopped', 'system')
                            logger.info(f"Stopped followup for {sc_name} ({sc_lead['email']}) — same company as {lead_name} who replied")
                        conn.commit()
            except Exception as company_err:
                logger.warning(f"Company-level followup stop failed: {company_err}")

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
                        html_content=markdown_to_html(lead_confirm_body),
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
    
    # Attempt to read from Redis cache first
    cache_key = f"inbound_deals:{uid}:{page}:{per_page}"
    if redis_available and redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"INFO: Cache HIT for inbound deals of user {uid} on page {page}")
                return json.loads(cached)
        except Exception as ce:
            logger.warning(f"WARNING: Redis cache read error: {ce}")
            
    offset = (page - 1) * per_page
    try:
        # Total Bypass: If a meeting exists, it must show up. Otherwise, show replied leads.
        print(f"DEBUG: Fetching inbound deals for uid: {uid} (Original X-User-Id: {user_id})")
        if user_id == "admin":
            count_query = "SELECT COUNT(*) FROM leads_raw WHERE meeting_time IS NOT NULL OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED', 'CLOSED'))"
            cur.execute(count_query)
            count_result = cur.fetchone()
            total = count_result['count'] if count_result else 0
            
            query = """
                SELECT id, first_name, last_name, email, company_name, persona, fit_score,
                       email_status, is_responded, reply_intent, deal_size, pitch_deck_url,
                       meeting_time, meeting_link, updated_at, created_at,
                       rag_intelligence, remarks, phone, linkedin_url, source, user_id
                FROM leads_raw 
                WHERE meeting_time IS NOT NULL 
                OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED', 'CLOSED'))
                ORDER BY updated_at DESC LIMIT %s OFFSET %s
            """
            cur.execute(query, (per_page, offset))
            leads = cur.fetchall()
        else:
            count_query = "SELECT COUNT(*) FROM leads_raw WHERE user_id = %s AND (meeting_time IS NOT NULL OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED', 'CLOSED')))"
            cur.execute(count_query, (uid,))
            count_result = cur.fetchone()
            total = count_result['count'] if count_result else 0
            
            query = """
                SELECT id, first_name, last_name, email, company_name, persona, fit_score,
                       email_status, is_responded, reply_intent, deal_size, pitch_deck_url,
                       meeting_time, meeting_link, updated_at, created_at,
                       rag_intelligence, remarks, phone, linkedin_url, source, user_id
                FROM leads_raw 
                WHERE user_id = %s 
                AND (meeting_time IS NOT NULL OR (is_responded = TRUE AND email_status IN ('SENT', 'REPLIED', 'CLOSED')))
                ORDER BY updated_at DESC LIMIT %s OFFSET %s
            """
            cur.execute(query, (uid, per_page, offset))
            leads = cur.fetchall()
        
        # PROACTIVE FILENAME RECOVERY for historical leads (Cleaned)
        import re
        INTERNAL_PDFS = ['profile.pdf', 'intro.pdf', 'deck.pdf', 'onepager.pdf', 'company_profile.pdf', 'teaser.pdf']
        
        def extract_pdf_name(text):
            if not text: return None
            # Scan for patterns like <Name.pdf> or Name_Deck.pdf
            matches = re.findall(r'([a-zA-Z0-9_\-\s]+\.pdf)', str(text))
            for m in matches:
                name = m.strip()
                if not any(internal in name.lower() for internal in INTERNAL_PDFS):
                    return name
            return None

        processed_leads = []
        for l in leads:
            lead_dict = dict(l)
            # Ensure rag_intelligence is a dict for processing
            intel = lead_dict.get('rag_intelligence')
            if isinstance(intel, str):
                try: intel = json.loads(intel)
                except: intel = {}
            
            if not intel: intel = {}

            # If filename is missing, try to recover it from other fields
            if not intel.get('filename'):
                recovered = extract_pdf_name(lead_dict.get('remarks')) or \
                            extract_pdf_name(lead_dict.get('pitch_deck_url')) or \
                            extract_pdf_name(lead_dict.get('rag_advice'))
                if recovered:
                    intel['filename'] = recovered
                    lead_dict['rag_intelligence'] = intel
            
            processed_leads.append(lead_dict)

        print(f"DEBUG: Found {len(processed_leads)} leads for uid {uid}. Total count in DB: {total}")
        
        result = {
            "leads": processed_leads,
            "total": total,
            "page": page,
            "per_page": per_page
        }
        
        if redis_available and redis_client:
            try:
                # Cache results for 15 seconds so pagination & reloads are instant, but fresh data is fetched frequently
                redis_client.setex(cache_key, 15, json.dumps(result, cls=DateTimeEncoder))
                logger.info(f"INFO: Cached inbound deals for user {uid} on page {page}")
            except Exception as ce:
                logger.warning(f"WARNING: Redis cache write error: {ce}")
                
        return result
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
        # Queries for: replies (Re:), forwards (Fwd:), or keywords like pitch, deck, interested, not interested, meeting
        search_query = 'label:INBOX -from:me (subject:Re OR subject:Fwd OR "pitch" OR "deck" OR "interested" OR "intro" OR "meeting" OR "call")'
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
            
            invalidate_inbound_deals_cache(str(uid))
            return {"status": "success", "processed": len(messages), "detected": found_count}
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"Error in manual sync-inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmail/sync-drafts")
def get_gmail_sync_drafts(user_id: Optional[str] = Header(None, alias="X-User-Id"), refresh: bool = False):
    """Fetches real-time drafts directly from the user's Gmail account.
    Results are cached for 2 minutes; pass ?refresh=true to force a fresh fetch."""
    uid = normalize_user_id(user_id)
    try:
        if refresh:
            from app.services.google_service import _drafts_cache
            _drafts_cache.pop(int(uid), None)
        drafts = list_gmail_drafts(int(uid))
        return drafts
    except Exception as e:
        print(f"Error fetching Gmail sync drafts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmail/sync-sent")
def get_gmail_sync_sent(user_id: Optional[str] = Header(None, alias="X-User-Id"), refresh: bool = False):
    """Fetches real-time sent messages directly from the user's Gmail account.
    Results are cached for 2 minutes; pass ?refresh=true to force a fresh fetch."""
    uid = normalize_user_id(user_id)
    try:
        if refresh:
            from app.services.google_service import _sent_cache
            _sent_cache.pop(int(uid), None)
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
        res = send_email(
            to_email=lead['email'],
            subject=f"Meeting Scheduled: {lead_name} x LeadStream",
            html_content=markdown_to_html(confirm_body),
            from_email=sender_user['email'],
            from_name=sender_user['full_name'],
            is_system_email=False,
            user_id=uid
        )
        success = res[0] if isinstance(res, tuple) else res
        
        invalidate_inbound_deals_cache(str(uid))
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
                html_content=markdown_to_html(reschedule_body),
                from_email=sender_email,
                from_name=sender_user['full_name'] if sender_user else "LeadStream Team",
                is_system_email=False,
                user_id=uid
            )

        invalidate_inbound_deals_cache(str(uid))
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

# Global cache to prevent redundant Gmail API calls
INBOX_CACHE = {}
CACHE_EXPIRY = 60 # seconds

@router.get("/gmail/inbox")
def get_unified_inbox(user_id: Optional[str] = Header(None, alias="X-User-Id"), refresh: bool = False):
    """Fetches a list of the latest replies/messages with 60s caching for speed.
    Pass ?refresh=true to bypass cache and force a fresh fetch."""
    from app.services.google_service import get_gmail_service
    uid = normalize_user_id(user_id)
    
    # Bypass cache if refresh requested
    if refresh:
        INBOX_CACHE.pop(uid, None)
    
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
    import re
    
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
                messages = results.get('messages', [])
                
                for msg_meta in messages:
                    m_id = msg_meta['id']
                    
                    # PERSISTENT DEDUPLICATION: Skip immediately if already processed in DB
                    cur.execute("SELECT 1 FROM gmail_processed_messages WHERE message_id = %s", (m_id,))
                    if cur.fetchone():
                        continue
                    
                    try:
                        # Check if this thread/message is from a lead
                        msg = service.users().messages().get(userId='me', id=m_id, format='metadata').execute()
                        
                        # Skip if the message is sent BY the user
                        labels = msg.get('labelIds', [])
                        if 'SENT' in labels:
                            cur.execute("INSERT INTO gmail_processed_messages (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (m_id, uid))
                            conn.commit()
                            continue
                            
                        headers = msg.get('payload', {}).get('headers', [])
                        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
                        
                        # Extract pure email from "Name <email@site.com>"
                        email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
                        if email_match:
                            sender_email = email_match.group(0).lower()
                            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "")

                            # BOUNCE DETECTION: mailer-daemon, postmaster, or "Undeliverable" subject
                            is_bounce = any(x in sender.lower() for x in ['mailer-daemon', 'mailer.daemon', 'postmaster'])
                            is_bounce = is_bounce or 'undeliverable' in subject.lower()
                            if is_bounce:
                                try:
                                    # Use snippet from Gmail API (text preview) to extract failed recipient
                                    snippet = msg.get('snippet', '')
                                    failed_email_raw = re.search(r'[\w\.-]+@[\w\.-]+', snippet)
                                    bounce_reason = "Mail server rejected the message (Undeliverable)"
                                    
                                    # Fetch full message to get more details and extract recipient more reliably
                                    full_bounce = service.users().messages().get(userId='me', id=m_id, format='full').execute()
                                    from app.services.google_service import extract_message_body
                                    body_text = extract_message_body(full_bounce.get('payload', {}))
                                    
                                    if body_text:
                                        # Extract failed recipient from body if snippet failed
                                        if not failed_email_raw:
                                            failed_email_raw = re.search(r'[\w\.-]+@[\w\.-]+', body_text)
                                        
                                        # Extract specific reason if possible (e.g., 550 error codes)
                                        # Common pattern in Gmail bounces: "The response from the remote server was: 550 ..."
                                        reason_match = re.search(r'(?:response from the remote server was:|Diagnostic-Code:).*?\n\s*(.*?)(?:\n|$)', body_text, re.IGNORECASE | re.DOTALL)
                                        if reason_match:
                                            bounce_reason = f"Server Response: {reason_match.group(1).strip()[:150]}"
                                        elif "inbox is full" in body_text.lower():
                                            bounce_reason = "Recipient's inbox is full"
                                        elif "spam" in body_text.lower() or "blocked" in body_text.lower():
                                            bounce_reason = "Message blocked by recipient's spam filter"

                                    if failed_email_raw:
                                        failed_email = failed_email_raw.group(0).lower()
                                        cur.execute("""
                                            SELECT id, email_status FROM leads_raw 
                                            WHERE LOWER(email) = %s AND email_status != 'BOUNCED'
                                            LIMIT 1
                                        """, (failed_email,))
                                        bounced_lead = cur.fetchone()
                                        if bounced_lead:
                                            cur.execute("UPDATE leads_raw SET email_status = 'BOUNCED', followup_status = 'STOPPED', updated_at = NOW() WHERE id = %s", (bounced_lead['id'],))
                                            conn.commit()
                                            from app.models.lead import add_activity_log
                                            add_activity_log(bounced_lead['id'], 'BOUNCED', f'Email bounced — {bounce_reason}', 'system')
                                            logger.info(f"Marked lead {bounced_lead['id']} ({failed_email}) as BOUNCED. Reason: {bounce_reason}")
                                except Exception as bounce_err:
                                    logger.warning(f"Bounce processing failed for msg {m_id}: {bounce_err}")
                                cur.execute("INSERT INTO gmail_processed_messages (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (m_id, uid))
                                conn.commit()
                                continue

                            # Check if this email exists as a lead (regardless of owner) and hasn't responded yet
                            cur.execute("""
                                SELECT id, user_id FROM leads_raw 
                                WHERE LOWER(email) = LOWER(%s) AND is_responded = FALSE
                                LIMIT 1
                            """, (sender_email,))
                            
                            found_lead = cur.fetchone()
                            if found_lead:
                                target_uid = found_lead['user_id'] or uid
                                
                                # Fetch full message data for classification
                                try:
                                    full_msg_data = service.users().messages().get(userId='me', id=m_id, format='full').execute()
                                    handle_potential_reply(target_uid, full_msg_data.get('threadId'), full_msg_data)
                                    conn.commit()
                                except Exception as fetch_err:
                                    print(f"Error fetching full message for polling: {fetch_err}")
                        
                        # Mark as processed in DB
                        cur.execute("INSERT INTO gmail_processed_messages (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (m_id, uid))
                        conn.commit()
                    except Exception as msg_err:
                        print(f"Error processing single message {m_id}: {msg_err}")
                        continue
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
        from app.services.google_service import get_gmail_service, extract_attachments
        import requests
        import psycopg2.extras
        import json
        import re
        import os
        
        service = get_gmail_service(int(user_id))
        if not service:
            return {"success": False, "error": "Gmail service not initialized for this user"}
            
        # Scan Gmail for PDFs (all messages, not just Inbox)
        results = service.users().messages().list(userId='me', q='has:attachment filename:pdf', maxResults=50).execute()
        messages = results.get('messages', [])
        
        count = 0
        rag_url = "https://rag-sys-gz59.onrender.com"
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            for msg in messages:
                try:
                    msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                    headers = msg_data.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
                    
                    match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
                    sender_email = match.group(0).lower() if match else sender.lower()
                    
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
                        
                        rag_category = None
                        rag_advice = None
                        rag_intel = None
                        
                        try:
                            files = {'file': (pdf_attachment['filename'], pdf_attachment['data'])}
                            # Send to RAG
                            rag_res = requests.post(f"{rag_url}/process", files=files, timeout=300, verify=False)
                            if rag_res.status_code == 200:
                                rag_data = rag_res.json()
                                rag_item_id = rag_data.get('id')
                                if rag_item_id:
                                    import time
                                    for _ in range(30):
                                        st_res = requests.get(f"{rag_url}/status/{rag_item_id}", timeout=60, verify=False)
                                        if st_res.status_code == 200:
                                            st_data = st_res.json()
                                            if st_data.get('status', '').lower() in ['completed', 'success']:
                                                ins = st_data.get('insights', {})
                                                if ins:
                                                    rag_advice = ins.get('summary') or ins.get('verdict')
                                                    rag_category = (ins.get('type') or ins.get('category') or 'INVESTOR').upper()
                                                    rag_intel = {
                                                        "answer": rag_advice,
                                                        "source": "Pure Llama 3.1 (RAG Engine)",
                                                        "category": rag_category,
                                                        "strategy": ins.get('strategy', {}),
                                                        "actuals": ins.get('actuals', {}),
                                                        "full_insights": ins
                                                    }
                                                break
                                        time.sleep(10)
                        except Exception as e:
                            print(f"RAG Retro Error for {sender_email}: {e}")
     
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
                                print(f"Failed to generate retro draft for {sender_email}: {draft_err}")
     
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
                        conn.commit()
                        count += 1
                except Exception as e:
                    print(f"Error retro syncing message {msg['id']}: {e}")
            
            return {"success": True, "updated_deals": count, "message": f"Retro-sync complete. {count} pitch decks processed and classified."}
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"Retro sync error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/gmail/heal-threads")
def heal_gmail_threads(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Retroactively heals Gmail thread IDs for all SENT leads with missing gmail_thread_id.
    Scans the Gmail Sent folder, matches emails by recipient address, and populates
    gmail_thread_id + gmail_message_id so all future follow-ups nest correctly.
    """
    import re as _re
    uid = normalize_user_id(user_id)

    service = get_gmail_service(int(uid))
    if not service:
        raise HTTPException(status_code=400, detail="Gmail not connected. Please link your Google account first.")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # 1. Find all sent leads that are missing gmail_thread_id for this user
        cur.execute("""
            SELECT id, email, last_outreach_subject, first_outreach_subject
            FROM leads_raw
            WHERE user_id = %s
              AND email_status = 'SENT'
              AND (gmail_thread_id IS NULL OR gmail_thread_id = '')
              AND followup_status = 'ACTIVE'
        """, (uid,))
        broken_leads = cur.fetchall()

        if not broken_leads:
            return {"status": "ok", "healed": 0, "message": "All leads already have Gmail thread IDs. Nothing to heal."}

        # Build a lookup: recipient email → lead row
        leads_by_email = {row['email'].lower().strip(): dict(row) for row in broken_leads}
        logger.info(f"Found {len(leads_by_email)} leads with missing gmail_thread_id for user {uid}. Scanning Sent folder...")

        # 2. Scan Sent folder (last 500 messages) to match by recipient
        results = service.users().messages().list(
            userId='me', q='in:sent', maxResults=500
        ).execute()
        sent_msgs = results.get('messages', [])

        healed = 0
        for meta in sent_msgs:
            if not leads_by_email:
                break  # All leads healed, stop early

            try:
                msg = service.users().messages().get(
                    userId='me',
                    id=meta['id'],
                    format='metadata',
                    metadataHeaders=['To', 'Message-ID', 'Message-Id', 'message-id', 'Subject']
                ).execute()

                headers = msg.get('payload', {}).get('headers', [])
                to_raw = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
                subject_raw = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
                msg_id_raw = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)

                # Extract all recipient emails from To header
                recipient_emails = [e.lower().strip() for e in _re.findall(r'[\w\.\-\+]+@[\w\.\-]+', to_raw)]

                for recip in recipient_emails:
                    if recip in leads_by_email:
                        lead = leads_by_email[recip]
                        thread_id = msg.get('threadId')
                        rfc_msg_id = msg_id_raw

                        if not rfc_msg_id:
                            # Fetch full metadata for RFC Message-ID
                            try:
                                full_meta = service.users().messages().get(
                                    userId='me', id=meta['id'], format='metadata',
                                    metadataHeaders=['Message-ID', 'Message-Id', 'message-id']
                                ).execute()
                                full_headers = full_meta.get('payload', {}).get('headers', [])
                                rfc_msg_id = next((h['value'] for h in full_headers if h['name'].lower() == 'message-id'), None)
                            except Exception:
                                rfc_msg_id = f"<{meta['id']}@mail.gmail.com>"

                        if thread_id:
                            cur.execute("""
                                UPDATE leads_raw
                                SET gmail_thread_id = %s,
                                    gmail_message_id = %s,
                                    first_outreach_subject = COALESCE(first_outreach_subject, %s),
                                    updated_at = NOW()
                                WHERE id = %s
                            """, (thread_id, rfc_msg_id, subject_raw, lead['id']))
                            conn.commit()

                            logger.info(f"✅ Healed thread for lead {lead['id']} ({recip}): thread={thread_id}")
                            healed += 1
                            del leads_by_email[recip]  # Remove from pending list
                            break

            except Exception as msg_err:
                logger.warning(f"Could not process sent message {meta['id']}: {msg_err}")
                continue

        still_missing = len(leads_by_email)
        return {
            "status": "complete",
            "healed": healed,
            "still_missing": still_missing,
            "message": f"Healed {healed} leads. {still_missing} leads could not be matched (emails may not be in Sent folder)."
        }

    except Exception as e:
        logger.error(f"heal_gmail_threads error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

