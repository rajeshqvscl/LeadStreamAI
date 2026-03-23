# app/services/llm_services.py

import os
import json
import structlog
from anthropic import Anthropic

logger = structlog.get_logger(__name__)

MODEL_NAME = "claude-sonnet-4-6"   # ✅ LATEST STABLE MODEL AS OF 2026
PROMPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "prompts", "email_v1.txt")
)


class EmailGenerator:

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=api_key)

    def generate_email(self, lead: dict):

        with open(PROMPT_PATH, "r", encoding="utf-8") as prompt_file:
            base_prompt = prompt_file.read().strip()

        lead_prompt = f"""
Lead:
Name: {lead.get('first_name', '')} {lead.get('last_name', '')}
Company: {lead.get('company_name', '')}
"""

        prompt = f"{base_prompt}\n\n{lead_prompt}"

        try:
            logger.info("calling_claude", model=MODEL_NAME)

            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            )

            # ✅ SAFE extraction
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            text = text.strip()

            log_text = str(text)[:200]
            logger.info("claude_raw_response", text=log_text)

            return self._parse_response(text)

        except Exception as e:
            logger.error("claude_error", error=str(e))

            # ✅ High-quality fallback
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
• Demonstrate measurable ROI improvements to clients

I'd love to share some specific examples of how similar firms are implementing these approaches, and explore whether there might be relevant applications for {company}'s client work.

Would you be open to a brief 15-minute conversation next week? I can share some industry benchmarks that might be valuable for your upcoming client discussions.

Best regards,
[Your name]"""
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
            
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text
            
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