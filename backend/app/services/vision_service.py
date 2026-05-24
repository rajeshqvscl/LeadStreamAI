import os
import json
import base64
import structlog
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = structlog.get_logger(__name__)

ANALYSIS_PROMPT = """You are an expert at reverse-engineering email templates from screenshots.

Analyze this screenshot of an email template and extract its structure. Return ONLY valid JSON with these fields:
1. "subject": The exact subject line text (or empty string if not visible)
2. "body": The full email body text, preserving ALL formatting, bullet points, headings, bold/italic markers, spacing, and structure
3. "formatting_notes": Any observations about styling (font sizes, colors, alignment, etc.)

IMPORTANT RULES:
- Preserve the EXACT text including any placeholder variables like {{First Name}}, {{Company Name}} etc.
- Keep all bullet points, numbered lists, headings exactly as they appear
- Maintain paragraph breaks and spacing
- If you see markdown-style formatting (**bold**, *italic*), keep it
- If you see HTML tags, keep them
- Extract the Subject: line if visible

Respond with ONLY this JSON structure (no other text):
{
  "subject": "...",
  "body": "...",
  "formatting_notes": "..."
}"""

def analyze_template_screenshot(image_base64: str) -> dict:
    """Analyze a template screenshot using Gemini vision API and return extracted template structure."""
    
    # Try Gemini first
    try:
        import google.generativeai as genai
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            image_data = base64.b64decode(image_base64)
            
            response = model.generate_content([
                ANALYSIS_PROMPT,
                {"mime_type": "image/png", "data": image_data}
            ])
            
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0].strip()
            
            result = json.loads(text)
            logger.info("template_analysis_success", source="gemini")
            return result
    except Exception as e:
        logger.warning("gemini_vision_failed", error=str(e))
    
    # Fallback to Claude (Anthropic) vision
    try:
        from anthropic import Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            client = Anthropic(api_key=anthropic_key)
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64
                        }}
                    ]
                }]
            )
            
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0].strip()
            
            result = json.loads(text)
            logger.info("template_analysis_success", source="claude")
            return result
    except Exception as e:
        logger.error("all_vision_models_failed", error=str(e))
    
    return {"subject": "", "body": "", "formatting_notes": "Analysis failed - no vision-capable LLM available"}
