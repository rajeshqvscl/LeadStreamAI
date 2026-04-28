from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
import structlog
from app.services.llm_services import EmailGenerator

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
