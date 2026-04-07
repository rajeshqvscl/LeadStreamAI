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
        # Personalize greeting
        first_name = lead.get('first_name')
        if not first_name or str(first_name).strip().lower() == "there":
            # Fallback to full name if first name is missing or "there"
            first_name = lead.get('name') or lead.get('full_name') or lead.get('last_name') or ""
        
        greeting = f"Hi {first_name}," if first_name else "Hi,"
        
        body = f"""{greeting}
        
I hope you're doing well.

I'm {sender_name} from QVSCL (Gurugram), a strategic advisory firm working with high-growth early-stage ventures. We are currently raising a round for a platform building a vertical AI-powered hiring intelligence layer, combining AI agents, recruitment workflows, and trust-based verification infrastructure.

**Business Overview**
• Founded: By industry leaders with 20+ years of experience across HR, fintech, and enterprise technology
• Focus: Building a unified hiring infrastructure platform that automates and optimizes end-to-end recruitment workflows
• Platform Offering: A full-stack hiring platform integrating ATS, sourcing, screening, and background verification
• Technology: AI-powered vertical agents enabling sourcing, scheduling, interviewing, and verification workflows
• Revenue Model: Enterprise SaaS with multi-layered monetization
• Core Differentiation: A single unified platform combining hiring + verification + intelligence

**Industry Overview**
• 3.6M job vacancies are posted monthly in India, but only 2.1M hires are completed
• 1.5M workforce gap leading to significant unrealized economic output
• 80% of employers face talent shortages
• Hiring processes remain largely manual and fragmented

**Market Opportunity**
• Global Hiring & Recruitment Tech TAM: $150B+
• Rapid shift toward AI-driven automation, trust, and verification layers (35-45% CAGR)

**Problems**
*HR & Recruiter Challenges*
• 180 applications per hire leading to massive screening overload
• Recruiters managing higher workloads without increased team size
• 57% of time spent on repetitive data tasks

*Process Inefficiencies*
• Fragmented workflows across 20+ tools
• Manual data handling and long hiring cycles (44 days)

*Trust & Quality Issues*
• 70% resumes contain inaccuracies and AI-generated profiles flooding pipelines
• High attrition due to poor matching

**Solutions**
• AI Hiring Co-Pilot: Vertical AI agents automating sourcing and screening
• Unified Platform: End-to-end system integrating ATS and BGV
• Trust Infrastructure: Proprietary trust graph
• Background Verification: Native BGV system with 20+ checks
• Workflow Automation: Eliminates manual HR processes
• Scalable Architecture: APIs and integrations with HRMS/ATS

**Validations & Traction**
• 100K+ companies onboarded
• 250+ enterprise customers across 50+ industries
• 94% customer retention rate

**Operational Impact**
• Time-to-hire reduced from weeks to 2-3 days
• Verification TAT reduced from 15 days to 2 days
• 40%+ reduction in HR operational workload

**Fundraise**: $1M

If this aligns with your portfolio focus and does not conflict with it, I’d be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.

For more details about our services: [Website](https://qvscl.com/) | [Linkedin](https://www.linkedin.com/company/qvstrategicconsultingllp/?originalSubdomain=in)

Looking forward to your response.

--
Thanks & Regards,
{sender_name}"""

        return {
            "subject": "Quick introduction",
            "body": body
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
                max_tokens=4000,
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