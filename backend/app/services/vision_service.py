import os
import json
import base64
import structlog
import tempfile
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

TEXT_ANALYSIS_PROMPT = """You are an expert at structuring email templates from raw text.

Analyze this extracted text from an email template document and structure it. Return ONLY valid JSON with these fields:
1. "subject": The subject line (or "" if not found)
2. "body": The full email body with markdown formatting (preserve bullet points, headings, bold markers, spacing)
3. "formatting_notes": "Extracted from document text"

IMPORTANT RULES:
- Detect and add markdown formatting (**bold** for headings/labels)
- Add proper paragraph breaks and spacing
- If you see placeholder variables like {{First Name}}, {{Company Name}}, preserve them exactly
- Organize the content into a clean, professional email structure

Respond with ONLY this JSON structure:
{
  "subject": "...",
  "body": "...",
  "formatting_notes": "Extracted from document text"
}"""


def analyze_template_screenshot(image_base64: str) -> dict:
    """Analyze a template screenshot using Gemini vision API and return extracted template structure."""
    
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
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0].strip()
            
            result = json.loads(text)
            logger.info("template_analysis_success", source="gemini")
            return result
    except Exception as e:
        logger.warning("gemini_vision_failed", error=str(e))
    
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


def analyze_pdf_template(file_bytes: bytes, filename: str) -> dict:
    """Convert PDF pages to images and analyze with vision API."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        merged_subject = ""
        merged_body_parts = []
        merged_notes = []

        for page_num in range(min(len(doc), 5)):  # Max 5 pages
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            result = analyze_template_screenshot(img_b64)
            if result.get("subject") and not merged_subject:
                merged_subject = result["subject"]
            if result.get("body"):
                merged_body_parts.append(result["body"])
            if result.get("formatting_notes"):
                merged_notes.append(result["formatting_notes"])

        doc.close()
        return {
            "subject": merged_subject,
            "body": "\n\n".join(merged_body_parts) if merged_body_parts else "",
            "formatting_notes": " | ".join(merged_notes) if merged_notes else "Extracted from PDF"
        }
    except ImportError:
        logger.warning("pymupdf_not_available")
        return {"subject": "", "body": "", "formatting_notes": "PDF analysis requires PyMuPDF (fitz)"}
    except Exception as e:
        logger.error("pdf_analysis_failed", error=str(e))
        return {"subject": "", "body": "", "formatting_notes": f"PDF analysis failed: {str(e)}"}


def analyze_docx_template(file_bytes: bytes, filename: str) -> dict:
    """Extract text from DOCX and structure it via LLM."""
    try:
        from docx import Document
        import io
        doc = Document(io.BytesIO(file_bytes))
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        if not full_text.strip():
            return {"subject": "", "body": "", "formatting_notes": "No text found in document"}
        
        try:
            import google.generativeai as genai
            gemini_key = os.getenv("GEMINI_API_KEY")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                response = model.generate_content(f"{TEXT_ANALYSIS_PROMPT}\n\nEXTRACTED TEXT:\n{full_text[:10000]}")
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    text = text.rsplit("```", 1)[0].strip()
                return json.loads(text)
        except Exception as e:
            logger.warning("gemini_text_failed", error=str(e))
        
        return {"subject": "", "body": full_text, "formatting_notes": "Extracted from DOCX (no LLM formatting)"}
    except ImportError:
        logger.warning("python_docx_not_available")
        return {"subject": "", "body": "", "formatting_notes": "DOCX analysis requires python-docx"}
    except Exception as e:
        logger.error("docx_analysis_failed", error=str(e))
        return {"subject": "", "body": "", "formatting_notes": f"DOCX analysis failed: {str(e)}"}
