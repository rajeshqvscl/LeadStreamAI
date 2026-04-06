# app/services/llm_services.py

import os
import json
import structlog
from anthropic import Anthropic

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = structlog.get_logger(__name__)

MODEL_NAME = "claude-sonnet-4-6"

class EmailGenerator:

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=api_key)

    def _get_prompt(self, prompt_type: str):
        """Fetch prompt content from dedicated database table."""
        try:
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT content FROM prompts WHERE prompt_type = %s AND is_active = TRUE LIMIT 1", (prompt_type,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row['content'] if row else None
        except Exception as e:
            logger.error("error_fetching_prompt", type=prompt_type, error=str(e))
            return None

    def generate_email(self, lead: dict, sender_name: str = "the team"):
        # Fetch dynamic instructions from DB
        email_prompt = self._get_prompt("EMAIL_GENERATION")
        context_prompt = self._get_prompt("CONTEXT") or "We are a technology partner helping businesses with AI-driven efficiency."
        
        if not email_prompt:
             # High-quality default if DB is empty
             email_prompt = "You are a professional outreach expert. Write a concise, value-driven cold email."

        lead_info = f"""
Lead Information:
Name: {lead.get('first_name', '')} {lead.get('last_name', '')}
Company: {lead.get('company_name', '')}
Title/Role: {lead.get('designation', lead.get('persona', 'Executive'))}
Industry Context: {lead.get('industry', 'Technology')}

Sender Context:
Sender Name: {sender_name}
Company Mission: {context_prompt}
"""

        full_system_prompt = f"{email_prompt}\n\n{lead_info}\n\nIMPORTANT: Use the Sender Name provided in the sign-off. Return ONLY valid JSON with 'subject' and 'body' keys."

        try:
            logger.info("calling_claude", model=MODEL_NAME)

            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": full_system_prompt
                    }
                ],
            )
            
            # Extract text
            text = "".join([block.text for block in response.content if block.type == "text"]).strip()
            return self._parse_response(text)

        except Exception as e:
            logger.error("claude_error", error=str(e))

            # ✅ High-quality fallback with DYNAMIC NAME
            company = lead.get('company_name', 'your company')
            first_name = lead.get('first_name', 'there')
            designation = lead.get('designation', 'Managing Director')
            
            return {
                "subject": f"Strategic Value & Operational Efficiency for {company}",
                "body": f"""Hi {first_name},

I hope this finds you well. As {designation} at {company}, you're likely seeing firsthand how your clients are grappling with increasing pressure to streamline operations while maintaining service quality in today's competitive landscape.

I've been working with several professional services firms who are discovering that AI-powered workflow automation is becoming a key differentiator—not just for their own operations, but as a strategic advantage they can offer clients during engagements.

What's particularly interesting is how firms like yours are leveraging these solutions to:
• Reduce project delivery times by 30-40%
• Free up senior talent for higher-value strategic work
• Provide measurable ROI improvements to clients

I'd love to share some specific examples of how similar firms are implementing these approaches, and explore whether there might be relevant applications for {company}'s client work.

Would you be open to a brief 15-minute conversation next week? I can share some industry benchmarks that might be valuable for your upcoming client discussions.

Best regards,
{sender_name}"""
            }

    def refine_email(self, subject: str, body: str, instruction: str):
        """
        Refine an existing email based on instructions.
        """
        current_email = f"Subject: {subject}\n\nBody: {body}"
        
        prompt = f"""
        Current Email:
        {current_email}
        
        Instruction: {instruction}
        
        Please refine the email based on the instruction. Return ONLY valid JSON with 'subject' and 'body'.
        """
        
        try:
            logger.info("refining_email", model=MODEL_NAME)
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            
            text = "".join([block.text for block in response.content if block.type == "text"]).strip()
            return self._parse_response(text)
        except Exception as e:
            logger.error("refine_error", error=str(e))
            return {"subject": subject, "body": body, "error": str(e)}

    def _parse_response(self, text: str):
        """
        Robustly parse JSON from LLM response.
        Handles markdown blocks, text prefixes, and partial JSON.
        """
        logger.info("parsing_llm_response", text_length=len(text))
        
        # 1. Try to find JSON within markdown code blocks
        if "```" in text:
            blocks = text.split("```")
            for block in blocks:
                content = block.strip()
                if content.startswith("json"):
                    content = content[4:].strip()
                
                if content.startswith("{") and content.endswith("}"):
                    try:
                        data = json.loads(content)
                        if "subject" in data or "body" in data:
                            return {
                                "subject": str(data.get("subject") or "Quick introduction"),
                                "body": str(data.get("body") or "")
                            }
                    except:
                        continue
        
        # 2. Try to find the outermost { } pair anywhere in the text
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(text[start:end])
                return {
                    "subject": str(data.get("subject") or "Quick introduction"),
                    "body": str(data.get("body") or "")
                }
        except Exception as e:
            logger.warning("json_substring_parse_failed", error=str(e))

        # 3. Last resort: If it's not JSON, treat the whole thing as the body
        # but try to extract a subject if it looks like "Subject: ..."
        subject = "Quick introduction"
        body = text.strip()
        
        if "Subject:" in text:
            lines = text.split("\n")
            for line in lines:
                if line.strip().startswith("Subject:"):
                    subject = line.replace("Subject:", "").strip()
                    body = text.replace(line, "").strip()
                    break
        
        return {
            "subject": subject,
            "body": body
        }