from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
import structlog
from app.services.llm_services import EmailGenerator
import os
import requests
import json
import psycopg2
import psycopg2.extras
from app.database import get_db_connection
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()
logger = structlog.get_logger(__name__)

@router.post("/leads/auto-enrich-sectors")
async def auto_enrich_sectors(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Batched classification of leads into Investors vs Clients based on sophisticated keyword analysis.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Fetch all leads that need classification or are currently unrefined
        cur.execute("SELECT id, company_name, designation, remarks, sector, lead_type FROM leads_raw")
        leads = cur.fetchall()
        
        updated_count = 0
        for lid, company, designation, remarks, current_sector, current_type in leads:
            from app.utils.classification import infer_lead_classification
            new_type, new_sector = infer_lead_classification(company, designation, remarks, current_sector)
            
            # Update logic for Type
            type_changed = False
            if new_type != current_type:
                cur.execute("UPDATE leads_raw SET lead_type = %s WHERE id = %s", (new_type, lid))
                type_changed = True
                
            # Update logic for Sector
            sector_changed = False
            if new_sector != current_sector:
                cur.execute("UPDATE leads_raw SET sector = %s WHERE id = %s", (new_sector, lid))
                sector_changed = True
                
            if type_changed or sector_changed:
                updated_count += 1
                
        conn.commit()
        return {"success": True, "updated": updated_count}
    except Exception as e:
        logger.error("auto_enrich_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.post("/leads/ai-deep-classify")
async def ai_deep_classify(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Uses LLM to classify leads that keyword-matching couldn't identify.
    Targeted specifically at 'Other' or 'NULL' sectors.
    """
    try:
        llm = EmailGenerator()
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Fetch leads labeled as 'Other' or NULL
        cur.execute("""
            SELECT id, company_name, designation, remarks, email_draft
            FROM leads_raw 
            WHERE sector = 'Other' OR sector IS NULL 
            LIMIT 50
        """)
        leads = cur.fetchall()
        
        if not leads:
            return {"success": True, "message": "No 'Other' leads to classify."}
            
        updated = 0
        for lead in leads:
            # Combine all available context, especially the email draft which shows the outreach focus
            context = f"""
            Company: {lead['company_name']}
            Designation: {lead['designation']}
            Remarks: {lead['remarks']}
            Last Draft/Email Sent: {lead['email_draft'] or 'None'}
            """
            
            prompt = f"""
            Identify the Industry Sector for this lead based on the company information AND the content of the email sent/drafted.
            
            Context:
            {context}
            
            Rules:
            1. Look for keywords in the email content (e.g., if we mention 'defence tech', 'healthcare AI', 'SaaS platform').
            2. Choose ONE sector from: SaaS, FinTech, AI, Defence, Manufacturing, Healthcare, EdTech, AgriTech, E-commerce, CleanTech, Logistics, PropTech, Media, Consulting.
            3. If the email is about a specific technology (e.g., Defence), prioritize that.
            4. Output ONLY the sector name (1-2 words). No explanation.
            5. If truly unknown, output 'Other'.
            """
            
            try:
                new_sector = llm._call_llm(prompt, max_tokens=30)
                if new_sector:
                    new_sector = new_sector.strip().replace("Sector:", "").replace("*", "").strip()
                    # Basic sanitization
                    if len(new_sector) > 30: new_sector = new_sector[:30]
                    
                    if new_sector and new_sector.lower() != 'other':
                        cur.execute("UPDATE leads_raw SET sector = %s WHERE id = %s", (new_sector, lead['id']))
                        updated += 1
                
                # Add a small delay to avoid hitting rate limits (Free tier usually 5-15 RPM)
                import time
                time.sleep(1.5)
            except Exception as e:
                logger.error("ai_classify_error", lead_id=lead['id'], error=str(e))
                continue
                
        conn.commit()
        return {"success": True, "updated": updated}
    except Exception as e:
        logger.error("deep_classify_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

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

        # Download the file if it's a local static path
        file_data = None
        if pitch_deck_url and pitch_deck_url.startswith("http"):
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
        
        # --- STRICT RAG ONLY (STABLE SESSION) ---
        rag_url = "https://rag-sys-gz59.onrender.com"
        rag_category = lead.get('sector')
        rag_advice = None
        rag_intel = None

        logger.info(f"Attempting Deep Analysis for lead {lead_id}...")
        
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            s = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
            s.mount('https://', HTTPAdapter(max_retries=retries))
            
            # 0. Wake-Up Check
            try:
                s.get(rag_url, timeout=60, verify=False)
            except:
                pass

            if file_data:
                # 1. RAG Processing (PDF)
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
                                        # Use structured format
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
                                            "full_insights": insights
                                        }
                                        break
                                elif current_status == 'failed':
                                    break
                            time.sleep(10)
            else:
                # 1. RAG Processing (Text Fallback)
                import io
                lead_text = f"Lead Persona: {lead.get('persona')}\nCompany: {lead.get('company_name')}\nBody: {lead.get('remarks') or ''}"
                files = {'file': (f"lead_{lead_id}.txt", io.StringIO(lead_text).getvalue())}
                s.post(f"{rag_url}/ingest", files=files, timeout=60, verify=False)
                
                query_msg = f"Provide a strategic intelligence analysis for this lead. Persona: {lead.get('persona')}. Company: {lead.get('company_name')}. Context: {lead.get('remarks')[:500]}"
                query_res = s.post(f"{rag_url}/ask", params={"question": query_msg}, timeout=120, verify=False)
                if query_res.status_code == 200:
                    rag_data = query_res.json()
                    rag_advice = f"### TEXT ANALYSIS SUMMARY\n{rag_data.get('answer') or rag_data.get('response')}"
                    rag_intel = rag_data
                    rag_intel["answer"] = rag_advice
            
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
