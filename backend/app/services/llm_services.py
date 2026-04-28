# app/services/llm_services.py

import os
import json
import structlog
from anthropic import Anthropic
import google.generativeai as genai

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = structlog.get_logger(__name__)

CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
GEMINI_MODEL = "gemini-3-flash-preview"

REFINEMENT_PROMPT = """
You are an expert executive assistant. Your task is to refine the provided email draft based on the user's instruction.
Return ONLY the refined body of the email. Do not include any conversational text, explanations, or subject lines.
If formatting (bold/italic) is requested, use standard HTML tags: <b></b> and <i></i>.

Current Draft: {content}
Instruction: {instruction}

Refined Body:
"""

class EmailGenerator:

    def __init__(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")

        if not self.anthropic_key and not self.gemini_key:
            raise ValueError("No LLM API keys found (ANTHROPIC_API_KEY or GEMINI_API_KEY)")

        # Initialize Anthropic if key exists
        self.anthropic_client = None
        if self.anthropic_key:
            try:
                self.anthropic_client = Anthropic(api_key=self.anthropic_key)
            except Exception as e:
                logger.error("anthropic_init_failed", error=str(e))

        # Initialize Gemini if key exists
        self.gemini_model = None
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel(GEMINI_MODEL)
            except Exception as e:
                logger.error("gemini_init_failed", error=str(e))

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
        if not first_name or str(first_name).strip().lower() in ["there", "contact", ""]:
            first_name = lead.get('name') or lead.get('full_name') or lead.get('last_name')
            if (not first_name or str(first_name).strip() == "") and lead.get('email'):
                email_prefix = lead.get('email').split('@')[0]
                first_part = email_prefix.replace("_", ".").replace("-", ".").split(".")[0]
                first_name = first_part.capitalize()
        
        greeting = f"Hi {first_name}," if first_name else "Hi,"
        company_name = lead.get('company_name') or lead.get('company') or "your organization"
        
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

**Fundraise: $1M**

If this aligns with your portfolio focus and does not conflict with it, I’d be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.

For more details about our services: [Website](https://qvscl.com) | [Linkedin](https://www.linkedin.com/company/qvscl/)

Looking forward to your response.
"""
        return {
            "subject": f"Strategic Investment Opportunity: AI-Powered Hiring Infrastructure",
            "body": body
        }

    def generate_palak_email(self, lead: dict, sender_name: str = "the team"):
        """Generates an email using Palak Mam's specific structure."""
        first_name = lead.get('first_name') or lead.get('name', '').split(' ')[0]
        company_name = lead.get('company_name') or lead.get('company') or "your organization"
        
        greeting = f"Hi {first_name}," if first_name else "Hi,"
        
        body = f"""{greeting}

I hope you're having a productive week.

I’m {sender_name} from QVSCL. We’ve been closely following the recruitment tech space, and I wanted to reach out regarding a high-growth vertical AI hiring platform we are currently advising for their $1M fundraise.

What caught our attention about this platform is their ability to reduce time-to-hire from weeks to just 2-3 days using vertical AI agents that automate the entire sourcing and verification cycle.

**Key Highlights:**
• **Proven Traction**: 250+ enterprise customers and 100K+ companies onboarded.
• **Unified Stack**: Integration of ATS, Sourcing, and Background Verification in one platform.
• **Market Need**: Solving the 1.5M workforce gap in the Indian market specifically.

We believe this could be a strategic fit for your portfolio. I’ve attached the QVSCL profile for your reference.

Would you be open to a quick 10-minute sync to discuss this further? Alternatively, I can share the pitch deck for your initial review.

Best,
{sender_name}
"""
        return {
            "subject": f"Investment Memo: AI Hiring Infrastructure | Traction Update",
            "body": body
        }

    def refine_email(self, subject: str, body: str, action: str):
        """Refines an existing email draft based on AI instructions."""
        instructions = {
            "shorten": "Make the email more concise while keeping all key information. Aim for brevity.",
            "professional": "Rewrite the email to sound more formal, executive, and professional.",
            "fix": "Correct all grammar, spelling, and punctuation errors while improving flow.",
            "bold": "Identify the most important sentences or key business terms and make them bold using <b></b> tags for emphasis.",
            "italic": "Add slight emphasis to call-to-actions or expressive phrases using <i></i> tags.",
            "persuasive": "Make the email more compelling and persuasive to increase the chance of a meeting."
        }
        
        instruction = instructions.get(action, action)
        content = f"Subject: {subject}\n\n{body}"
        prompt = REFINEMENT_PROMPT.format(content=content, instruction=instruction)
        
        try:
            refined_text = ""
            if self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                refined_text = response.content[0].text.strip()
            elif self.gemini_model:
                response = self.gemini_model.generate_content(prompt)
                refined_text = response.text.strip()
            
            # Try to extract subject if AI included it
            new_subject = subject
            new_body = refined_text
            if "Subject:" in refined_text:
                parts = refined_text.split("\n\n", 1)
                new_subject = parts[0].replace("Subject:", "").strip()
                if len(parts) > 1:
                    new_body = parts[1].strip()
            
            return {"subject": new_subject, "body": new_body}
        except Exception as e:
            logger.error("ai_refine_failed", error=str(e))
            return {"subject": subject, "body": body}

    def classify_reply(self, text: str):
        """Analyzes a lead's reply to determine intent and extract details."""
        prompt = f"""
        Analyze this email reply from a potential investor/client and extract details in JSON format.
        
        REPLY:
        {text}
        
        JSON STRUCTURE:
        {{
          "intent": "MEETING_REQUESTED" | "INTERESTED" | "NEEDS_MORE_INFO" | "NOT_INTERESTED",
          "deal_size": "string or null",
          "has_pitch_deck": boolean,
          "pitch_deck_url": "string or null"
        }}
        """
        try:
            if self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text.strip()
            else:
                response = self.gemini_model.generate_content(prompt)
                text = response.text.strip()
            
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return {"intent": "INTERESTED"}
        except Exception as e:
            logger.error("classification_error", error=str(e))
            return {"intent": "INTERESTED"}