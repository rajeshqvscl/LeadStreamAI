from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
import structlog
from app.services.llm_services import EmailGenerator
import os
import requests
import json
from app.database import get_db_connection
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()
logger = structlog.get_logger(__name__)

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

@router.post("/chat")
async def intelligence_chat(req: ChatRequest):
    """
    Handles AI chat specifically restricted to sector intelligence and industry data.
    """
    try:
        llm = EmailGenerator()
        
        system_prompt = """
        You are the 'LeadStream Sector Intelligence AI'. 
        Your ONLY purpose is to answer questions about industry sectors, market trends, historical business data (2014-2024), and strategic intelligence.
        
        STRICT RULES:
        1. If the user asks about ANYTHING else (jokes, coding, personal help, unrelated topics), politely decline and state that you are restricted to Sector Intelligence.
        2. Focus on sectors like Defence, SaaS, AI, FinTech, and Manufacturing.
        3. Use a professional, data-driven, and strategic tone.
        4. If you don't know a specific historical detail, provide a general strategic outlook based on industry trends.
        """
        
        # Combine history for context
        full_prompt = f"{system_prompt}\n\nChat History:\n"
        for h in req.history[-5:]: # Last 5 messages for context
            role = "User" if h['role'] == 'user' else "AI"
            full_prompt += f"{role}: {h['content']}\n"
        
        full_prompt += f"\nUser Question: {req.message}\nAI:"
        
        # Use the internal _call_gemini or similar logic from EmailGenerator
        if llm.gemini_model:
            response = llm.gemini_model.generate_content(full_prompt)
            return {"response": response.text.strip()}
        elif llm.anthropic_client:
            # Fallback to Anthropic if Gemini not available
            from app.services.llm_services import CLAUDE_MODEL
            resp = llm.anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": full_prompt}]
            )
            return {"response": resp.content[0].text}
        
        raise HTTPException(status_code=500, detail="No LLM provider available")
        
    except Exception as e:
        logger.error("intelligence_chat_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-lead/{lead_id}")
async def analyze_lead_manually(lead_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Manually triggers RAG analysis for a specific lead if it has a pitch deck URL.
    """
    try:
        conn = get_db_connection()
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("SELECT * FROM leads_raw WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
            
        pitch_deck_url = lead.get('pitch_deck_url')
        if not pitch_deck_url:
            raise HTTPException(status_code=400, detail="No pitch deck found for this lead. Please upload or sync first.")

        # Download the file if it's a local static path
        file_data = None
        if pitch_deck_url.startswith("http"):
            try:
                if "static/pitch_decks" in pitch_deck_url:
                    rel_path = pitch_deck_url.split("static/")[1]
                    file_path = os.path.join("static", rel_path)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            file_data = f.read()
                
                if not file_data:
                    res = requests.get(pitch_deck_url, timeout=30)
                    if res.status_code == 200:
                        file_data = res.content
            except Exception as e:
                logger.warning(f"Download failed: {e}")
        
        if not file_data:
            raise HTTPException(status_code=400, detail="Could not retrieve pitch deck file for analysis.")

        # --- STRICT RAG ONLY (STABLE SESSION) ---
        rag_url = "https://rag-sys-gz59.onrender.com"
        rag_category = lead.get('sector')
        rag_advice = None
        rag_intel = None

        logger.info(f"Attempting Pure RAG analysis (Llama 3.1) for lead {lead_id}...")
        
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            s = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
            s.mount('https://', HTTPAdapter(max_retries=retries))
            
            # 0. Wake-Up Check (Increased to 60s for stability)
            try:
                s.get(rag_url, timeout=60, verify=False)
            except:
                pass

            # 1. RAG Processing
            files = {'file': (f"lead_{lead_id}.pdf", file_data)}
            process_res = s.post(f"{rag_url}/process", files=files, timeout=300, verify=False)
            
            if process_res.status_code == 200:
                rag_data = process_res.json()
                rag_category = rag_data.get('category') or rag_data.get('type')
                rag_item_id = rag_data.get('id')
                
                if rag_item_id:
                    # 2. Polling loop
                    import time
                    max_polls = 30
                    for poll in range(max_polls):
                        logger.info(f"Polling RAG status for ID {rag_item_id} (Attempt {poll+1}/30)...")
                        status_res = s.get(f"{rag_url}/status/{rag_item_id}", timeout=60, verify=False)
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
                                    logger.info(f"Native RAG Insights extracted successfully for lead {lead_id}")
                                    break
                            elif current_status == 'failed':
                                break
                        time.sleep(10)
            
            if not rag_advice:
                raise Exception("RAG Engine timeout or analysis failure.")

        except Exception as rag_err:
            logger.error(f"STRICT RAG ERROR: {rag_err}")
            raise HTTPException(status_code=500, detail=f"RAG Engine Connectivity Error: {str(rag_err)}")

        # Generate a fresh, RAG-backed draft immediately
        try:
            from app.services.llm_services import EmailGenerator
            generator = EmailGenerator()
            # Pass the raw lead data + the new RAG advice
            lead_data_for_draft = {**dict(lead), "rag_advice": rag_advice}
            fresh_draft = generator.generate_email(lead_data_for_draft)
            
            if fresh_draft:
                rag_intel["draft"] = fresh_draft.get('body')
                rag_intel["subject"] = fresh_draft.get('subject')
        except Exception as draft_err:
            logger.warning(f"Failed to generate immediate RAG draft: {draft_err}")

        # Update DB
        rag_intel_json = json.dumps(rag_intel)
        cur.execute("""
            UPDATE leads_raw 
            SET sector = COALESCE(%s, sector),
                rag_advice = %s,
                rag_intelligence = %s,
                email_draft = %s
            WHERE id = %s
        """, (rag_category or "INVESTOR", rag_advice, rag_intel_json, rag_intel.get("draft"), lead_id))
        conn.commit()
        
        return {
            "success": True,
            "message": "Pure RAG Intelligence Analysis completed",
            "category": rag_category,
            "advice": rag_advice,
            "source": "Llama 3.1 (Native)"
        }

    except Exception as e:
        logger.error("analyze_lead_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
