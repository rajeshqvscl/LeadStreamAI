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
        
        # 1. Fetch all leads that need classification or are currently unrefined, with owner name
        cur.execute("""
            SELECT l.id, l.company_name, l.designation, l.remarks, l.sector, l.lead_type, u.username 
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
        """)
        leads = cur.fetchall()
        
        updated_count = 0
        for lid, company, designation, remarks, current_sector, current_type, owner_name in leads:
            from app.utils.classification import infer_lead_classification
            new_type, new_sector = infer_lead_classification(company, designation, remarks, current_sector, owner_name)
            
            updates = []
            params = []
            
            if new_type != current_type:
                updates.append("lead_type = %s")
                params.append(new_type)
                
            if new_sector != current_sector:
                updates.append("sector = %s")
                params.append(new_sector)
                
            if updates:
                params.append(lid)
                cur.execute(f"UPDATE leads_raw SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s", tuple(params))
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
    deal_context: Optional[dict] = None

from fastapi.responses import StreamingResponse
import asyncio

@router.post("/chat/stream")
async def intelligence_chat_stream(req: ChatRequest):
    """
    Real-time Streaming: Stream chat responses token-by-token.
    """
    llm = EmailGenerator()
    intent = llm.detect_intent(req.message)
    
    async def event_generator():
        # Using a simple mock stream for now as internal clients might not support it
        # In production, this would call llm_service with stream=True
        full_text = llm._call_llm(f"Analyze this query with intent {intent}: {req.message}")
        if not full_text:
            yield "No response generated."
            return

        for word in full_text.split():
            yield word + " "
            await asyncio.sleep(0.05)

    return StreamingResponse(event_generator(), media_type="text/plain")

@router.post("/chat")
async def intelligence_chat(req: ChatRequest):
    """
    Handles AI chat with Query Intent Detection v2 and Citation Highlighting.
    """
    try:
        llm = EmailGenerator()
        
        # 1. Detect Intent
        intent = llm.detect_intent(req.message)
        logger.info("detected_intent", intent=intent)
        
        # 2. Include deal context if available
        deal_context = ""
        if req.deal_context:
            dc = req.deal_context
            deal_context = f"""
CURRENT DEAL CONTEXT:
- Company: {dc.get('company', 'N/A')}
- Sector: {dc.get('sector', 'N/A')}
- RAG Intelligence: {json.dumps(dc.get('rag_intel', {}), indent=2)}
- Analysis: {dc.get('rag_advice', 'No analysis available')}

Use this context to answer questions about the selected deal.
"""
        
        # 3. System prompts based on intent
        system_prompts = {
            "SUMMARY": "You are a Research Analyst. Provide a concise, structured summary of the lead's business potential.",
            "EXTRACTION": "You are a Data Specialist. Extract precise metrics (Revenue, Stage, Growth) from the context. Use [Source: X] for citations.",
            "COMPARISON": "You are a Strategic Analyst. Compare the requested leads across key business metrics.",
            "WEB_SEARCH": "You are a Market Intelligence Expert. Provide external market context and trends related to the industry.",
            "CHAT": "You are the LeadStream Sector Intelligence AI. Answer questions about industry sectors and market trends."
        }
        
        base_system = system_prompts.get(intent, system_prompts["CHAT"])
        
        system_prompt = f"""
{base_system}
{deal_context}
        
STRICT RULES:
1. For SUMMARY and EXTRACTION, always include citations in [Source: Section Name] format.
2. Maintain a professional, data-driven tone.
3. If you detect a COMPARISON intent but don't have multiple leads in context, ask the user which leads to compare.
4. Answer based on the deal context provided above.
"""
        
        # Combine history for context
        full_prompt = f"{system_prompt}\n\nChat History:\n"
        for h in req.history[-5:]: # Last 5 messages for context
            role = "User" if h['role'] == 'user' else "AI"
            full_prompt += f"{role}: {h['content']}\n"
        
        full_prompt += f"\nUser Question: {req.message}\nIntent: {intent}\nAI:"
        
        response_text = llm._call_llm(full_prompt)
        
        if not response_text:
            raise HTTPException(status_code=500, detail="No LLM provider available")
            
        return {
            "response": response_text.strip(),
            "intent": intent,
            "citations_enabled": intent in ["SUMMARY", "EXTRACTION"]
        }
        
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
        
        cur.execute("SELECT id, first_name, last_name, email, company_name, persona, sector, lead_type, pitch_deck_url, remarks, email_draft FROM leads_raw WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
            
        pitch_deck_url = lead.get('pitch_deck_url')

        # Skip RAG analysis if the PDF is QVSCL's own company profile (not sent by the lead)
        if pitch_deck_url:
            pitch_lower = pitch_deck_url.lower()
            if any(x in pitch_lower for x in ['qvscl_company_profile', 'lalit_huria_profile']):
                pitch_deck_url = None  # treat as no PDF from lead

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
                    actual_url = pitch_deck_url
                    if "127.0.0.1" in pitch_deck_url or "localhost" in pitch_deck_url:
                        base = os.getenv("BACKEND_URL", "https://lead-backend-g9de.onrender.com")
                        path_part = pitch_deck_url.split("/static", 1)[1] if "/static" in pitch_deck_url else pitch_deck_url
                        actual_url = f"{base}/static{path_part}" if "/static" in pitch_deck_url else pitch_deck_url
                    res = requests.get(actual_url, timeout=30)
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
                    logger.info(f"RAG process response: {rag_data}")
                    
                    # Check if insights are in direct response
                    insights = rag_data.get('insights') or rag_data.get('summary')
                    if insights:
                        # Format verdict properly
                        verdict = rag_data.get('verdict') or 'NEUTRAL'
                        if verdict == 'N':
                            verdict = 'NEUTRAL'
                        elif verdict == 'P':
                            verdict = 'POSITIVE'
                        elif verdict == 'S':
                            verdict = 'STRONG'
                        
                        summary = rag_data.get('summary', '')
                        if summary and len(summary) < 10:
                            summary = 'Analysis complete. Review insights below for key metrics and signals.'
                        
                        def clean_val(v):
                            if not v:
                                return 'Not disclosed'
                            s = str(v)
                            # Remove ALL ** markers (bold markers anywhere)
                            s = s.replace('**', '')
                            return s.strip()
                        
                        rag_category = rag_data.get('category') or rag_data.get('type') or 'INVESTOR'
                        verdict_clean = clean_val(verdict)
                        summary_clean = clean_val(summary)
                        rag_advice = f"### RAG VERDICT\n{verdict_clean}\n\n"
                        rag_advice += f"### SUMMARY\n{summary_clean}\n\n"
                        
                        if rag_data.get('actuals'):
                            rag_advice += "### ACTUALS & METRICS\n"
                            for k, v in rag_data.get('actuals', {}).items():
                                rag_advice += f"- {k.replace('_', ' ').title()}: {clean_val(v)}\n"
                            rag_advice += "\n"
                        
                        if rag_data.get('strategy'):
                            rag_advice += "### STRATEGY RECOMMENDATION\n"
                            strat = rag_data.get('strategy', {})
                            priority = strat.get('priority', 'MEDIUM')
                            if len(priority) < 3:
                                priority = 'MEDIUM'
                            approach = strat.get('approach', 'Schedule a call to discuss further.')
                            rag_advice += f"- Priority: {priority}\n"
                            rag_advice += f"- Approach: {approach}\n\n"

                        rag_category = (rag_data.get('type') or rag_data.get('category') or 'INVESTOR').upper()
                        
                        rag_intel = {
                            "answer": rag_advice,
                            "source": "Pure Llama 3.1 (RAG Engine)",
                            "category": rag_category,
                            "sentiment_score": rag_data.get('score', 80),
                            "urgency_level": rag_data.get('strategy', {}).get('priority', 'MEDIUM').upper() if len(rag_data.get('strategy', {}).get('priority', 'MEDIUM')) > 3 else 'MEDIUM',
                            "strategy": rag_data.get('strategy', {}),
                            "actuals": rag_data.get('actuals', {}),
                            "signals": rag_data.get('breakdown', {}),
                            "key_signals": rag_data.get('key_signal'),
                            "verdict": verdict,
                            "full_insights": rag_data
                        }
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
                logger.warning("RAG Engine returned empty response. Falling back to local LLM analysis.")
                # Fallback to local LLM analysis
                prompt = f"""
                Perform a Deep Strategy Analysis for this lead.
                
                LEAD: {lead.get('first_name')} {lead.get('last_name')}
                COMPANY: {lead.get('company_name')}
                REMARKS: {lead.get('remarks')}
                
                Return ONLY a JSON object with this exact structure:
                {{
                  "verdict": "Detailed recommendation based on context",
                  "summary": "Summary of business potential",
                  "actuals": {{"revenue": "Extracted value or 'Not disclosed'", "orders": "Extracted value or 'Not disclosed'", "margin": "Extracted value or 'Not disclosed'"}},
                  "strategy": {{"priority": "HIGH/MEDIUM/LOW", "next_step": "Specific action", "reason": "Rationale"}},
                  "key_signals": "Specific business signals",
                  "score": 0-100
                }}
                """
                from app.services.llm_services import EmailGenerator
                gen = EmailGenerator()
                raw_res = gen._call_llm(prompt)
                try:
                    structured = json.loads(raw_res)
                    rag_advice = f"### RAG VERDICT\n{structured.get('verdict')}\n\n### SUMMARY\n{structured.get('summary')}"
                    rag_intel = structured
                    rag_intel["answer"] = rag_advice
                except:
                    rag_advice = raw_res
                    rag_intel = {"answer": rag_advice, "status": "LOCAL_AI_FALLBACK"}

        except Exception as rag_err:
            logger.error(f"STRICT RAG ERROR: {rag_err}")
            rag_intel = {
                "answer": f"Analysis failed: {str(rag_err)}",
                "actuals": {"Status": "Error"},
                "strategy": {"priority": "LOW", "next_step": "Retry Analysis"}
            }

        # --- INTEGRATE AGENT SERVICE (ENHANCED) ---
        try:
            from app.services.agent_service import AgentService
            agent = AgentService()
            
            # 1. Detect contradictions between DB and RAG
            contradictions = agent.detect_contradictions(dict(lead), rag_intel)
            if contradictions:
                rag_intel["contradictions"] = contradictions
                rag_advice += f"\n\n### CONTRADICTIONS DETECTED\n- " + "\n- ".join(contradictions)
            
            # 2. Generate Deep Autonomous Report
            deep_report = agent.generate_autonomous_report(lead_id)
            rag_intel["deep_report"] = deep_report
            
        except Exception as agent_err:
            logger.error(f"Agent Service Error: {agent_err}")
            rag_intel["agent_error"] = str(agent_err)

        # 3. Generate a fresh, RAG-backed draft immediately
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
            "message": "Advanced RAG Analysis with Agentic Checks completed",
            "category": rag_category,
            "advice": rag_advice,
            "rag_intel": rag_intel,
            "contradictions": rag_intel.get("contradictions", []),
            "source": "Llama 3.1 (Agent Augmented)"
        }

    except Exception as e:
        logger.error("analyze_lead_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.post("/compare-leads")
async def compare_leads(lead_ids: List[int], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Multi-Document Comparison: Aggregates insights across multiple leads for side-by-side analysis.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Fetch data for all requested leads
        cur.execute("SELECT id, company_name, sector, rag_advice, rag_intelligence FROM leads_raw WHERE id = ANY(%s)", (lead_ids,))
        leads = cur.fetchall()
        
        if not leads:
            raise HTTPException(status_code=404, detail="No leads found for comparison")
            
        # 2. Aggregate context for LLM
        comparison_context = "LEADS TO COMPARE:\n\n"
        for lead in leads:
            intel = lead.get('rag_intelligence')
            if isinstance(intel, str): intel = json.loads(intel)
            
            comparison_context += f"LEAD ID: {lead['id']}\n"
            comparison_context += f"Company: {lead['company_name']}\n"
            comparison_context += f"Sector: {lead['sector']}\n"
            comparison_context += f"Intelligence: {lead['rag_advice'] or 'No data'}\n"
            if intel and intel.get('actuals'):
                comparison_context += f"Metrics: {json.dumps(intel['actuals'])}\n"
            comparison_context += "---\n\n"
            
        # 3. Prompt for side-by-side comparison
        prompt = f"""
        You are a Venture Capital Analyst. Compare the following leads side-by-side.
        Create a Markdown table comparing them on:
        1. Sector Focus
        2. Key Metrics (Revenue/Stage/Growth)
        3. Strategic Verdict
        4. Primary Risk Flag
        
        CONTEXT:
        {comparison_context}
        
        Rules:
        - Use professional terminology.
        - If data is missing for a lead, mark it as 'N/A'.
        - Highlight the 'Winner' in terms of investment potential with an emoji.
        """
        
        llm = EmailGenerator()
        comparison_report = llm._call_llm(prompt, max_tokens=2048)
        
        return {
            "success": True,
            "report": comparison_report,
            "lead_count": len(leads)
        }
        
    except Exception as e:
        logger.error("compare_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/admin/rag-debug")
async def get_rag_debug_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Retrieval Debug Panel: Returns performance and health metrics for the RAG system.
    """
    # Simple role check
    if str(user_id).lower() != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
        
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Latency & Health (Ping external RAG)
        rag_url = "https://rag-sys-gz59.onrender.com"
        import time
        start = time.time()
        health = "OFFLINE"
        latency = 0
        try:
            res = requests.get(rag_url, timeout=5, verify=False)
            latency = round((time.time() - start) * 1000, 2)
            if res.status_code == 200: health = "ONLINE"
        except: pass
        
        # 2. Database Stats
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE rag_intelligence IS NOT NULL")
        analyzed_leads = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM activity_log WHERE action = 'REPORT_GENERATED'")
        reports_count = cur.fetchone()[0]
        
        return {
            "status": health,
            "latency_ms": latency,
            "engine": "Llama 3.1 (RAG Native)",
            "analyzed_leads": analyzed_leads,
            "reports_generated": reports_count,
            "active_tasks": ["Contradiction Detection", "Web-Augmented RAG", "Intent Classification"]
        }
        
    except Exception as e:
        logger.error("rag_debug_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/leads/{lead_id}/ai-timeline")
async def get_lead_ai_timeline(lead_id: int):
    """
    Summarizes the journey of a lead from ingestion to current state using LLM.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Fetch Lead basic info
        cur.execute("SELECT first_name, last_name, company_name, created_at, remarks, sector, lead_type FROM leads_raw WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
            
        # 2. Fetch Activity Logs
        cur.execute("SELECT action, details, created_at FROM activity_log WHERE lead_id = %s ORDER BY created_at ASC", (lead_id,))
        logs = cur.fetchall()
        
        # 3. Format context for LLM
        timeline_events = [f"- {lead['created_at'].strftime('%Y-%m-%d')}: Lead Ingested (Source: {lead['company_name']})"]
        if lead['remarks']:
            timeline_events.append(f"- Initial Remarks: {lead['remarks']}")
            
        for log in logs:
            timeline_events.append(f"- {log['created_at'].strftime('%Y-%m-%d')}: {log['action']} ({log['details'] or 'No details'})")
            
        context = "\n".join(timeline_events)
        
        # 4. Prompt for AI Story
        prompt = f"""
        Summarize the business journey of this lead based on the activity logs below. 
        Output EXACTLY 3 bullet points. Each point should start with a relevant emoji.
        Focus on the narrative (how it started, what happened, and where it is now).
        
        Logs:
        {context}
        
        Rules:
        - Professional but engaging tone.
        - Maximum 20 words per bullet point.
        - Output ONLY the 3 bullet points.
        """
        
        llm = EmailGenerator()
        summary = "AI summary generation failed."
        try:
            summary = llm._call_llm(prompt, max_tokens=200)
            if summary:
                summary = summary.strip()
        except Exception as e:
            logger.error("timeline_ai_error", error=str(e))
            
        return {
            "success": True,
            "lead_id": lead_id,
            "ai_summary": summary,
            "full_timeline": [
                {"date": lead['created_at'].strftime('%b %d, %Y'), "action": "Ingested", "details": f"Lead added for {lead['company_name']}"}
            ] + [{"date": l['created_at'].strftime('%b %d, %Y'), "action": l['action'], "details": l['details']} for l in logs]
        }
        
    except Exception as e:
        logger.error("get_timeline_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
