# app/services/llm_services.py

import os
import json
import structlog
from anthropic import Anthropic
from groq import Groq

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = structlog.get_logger(__name__)

CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
GEMINI_MODEL = "gemini-3-flash-preview"
GROQ_MODEL = "llama-3.3-70b-versatile"

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
        self.groq_key = os.getenv("GROQ_API_KEY")

        if not self.anthropic_key and not self.gemini_key and not self.groq_key:
            raise ValueError("No LLM API keys found (ANTHROPIC, GEMINI, or GROQ)")

        # Initialize clients
        self.anthropic_client = None
        if self.anthropic_key:
            try: self.anthropic_client = Anthropic(api_key=self.anthropic_key)
            except Exception as e: logger.error("anthropic_init_failed", error=str(e))

        self.groq_client = None
        if self.groq_key:
            try: self.groq_client = Groq(api_key=self.groq_key)
            except Exception as e: logger.error("groq_init_failed", error=str(e))

        self.gemini_model = None
        if self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel(GEMINI_MODEL)
            except Exception as e: logger.error("gemini_init_failed", error=str(e))

    def _call_llm(self, prompt: str, max_tokens: int = 1024):
        """Internal helper to call available LLMs in priority: Groq -> Gemini -> Claude."""
        
        # 1. Try Groq (Priority 1)
        if self.groq_client:
            try:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=GROQ_MODEL,
                    max_tokens=max_tokens
                )
                return chat_completion.choices[0].message.content.strip()
            except Exception as e:
                if "429" in str(e) or "limit" in str(e).lower():
                    logger.error("!!! GROQ KEY EXHAUSTED !!! Falling back to Gemini...")
                else:
                    logger.warning("groq_failed", error=str(e))

        # 2. Try Gemini (Priority 2)
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                if "429" in str(e) or "limit" in str(e).lower():
                    logger.error("!!! GEMINI KEY EXHAUSTED !!! Falling back to Claude...")
                else:
                    logger.warning("gemini_failed", error=str(e))

        # 3. Try Anthropic (Claude) (Final Fallback)
        if self.anthropic_client:
            try:
                response = self.anthropic_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
            except Exception as e:
                if "429" in str(e) or "limit" in str(e).lower():
                    logger.error("!!! CLAUDE KEY EXHAUSTED !!! No more fallback options.")
                else:
                    logger.error("claude_failed", error=str(e))
        
        return None

    def generate_email(self, lead: dict, sender_name: str = "the team", sender_linkedin: str = "https://www.linkedin.com/company/qvscl/"):
        """Generates a hyper-personalized email using RAG data if available, else falls back to standard template."""
        
        first_name = (lead.get('first_name') or lead.get('name') or "there").strip().capitalize()
        rag_advice = lead.get('rag_advice')
        
        # If we have RAG Intelligence, use LLM to craft a personalized version
        if rag_advice and len(rag_advice) > 100:
            prompt = f"""
            You are a senior investment associate at QVSCL (Gurugram). 
            Write a highly personalized outreach email to {first_name} based on the following RAG Intelligence.
            
            SENDER INFO:
            Name: {sender_name}
            Company: QVSCL
            LinkedIn: {sender_linkedin}
            
            RAG INTELLIGENCE DATA:
            {rag_advice}
            
            GUIDELINES:
            1. Maintain a professional, executive tone.
            2. Reference the specific metrics (Actuals) and sector insights from the RAG data.
            3. Keep the email concise (3-4 short paragraphs).
            4. Include a clear call-to-action (CTA) to schedule a meeting or share a deck.
            5. Use HTML tags <b></b> for key metrics or business terms.
            6. Do NOT include placeholder bracket text like [Your Name]. Use the provided sender info.
            7. Return ONLY the email subject and body separated by "---SUBJECT_END---".
            
            EXAMPLE OUTPUT FORMAT:
            Strategic Opportunity: [Topic] ---SUBJECT_END--- Hi [Name], ...
            """
            
            ai_response = self._call_llm(prompt, max_tokens=2048)
            if ai_response and "---SUBJECT_END---" in ai_response:
                parts = ai_response.split("---SUBJECT_END---", 1)
                return {
                    "subject": parts[0].strip(),
                    "body": parts[1].strip()
                }

        # FALLBACK: Standard Template (Only if RAG is unavailable)
        body = f"""Hi {first_name},

I hope you're doing well.

I'm {sender_name} from QVSCL (Gurugram), a strategic advisory firm working with high-growth early-stage ventures. We are currently raising a round for a <b>climate-focused agritech platform that is building a full-stack renewable energy marketplace for rural India.</b>

<b>Business Overview</b>
• <b>Sector</b>: Agritech / Climate / Social Impact
• <b>Stage</b>: Revenue-generating, growth-stage
• <b>Positioning</b>: India's first curated marketplace for renewable & green energy products for farmers and rural households
• <b>Platform Offering</b>:
    ◦ Multi-brand marketplace with <b>60+ brands and 200+ SKUs</b> across solar, biogas, and green energy solutions
    ◦ End-to-end solutions spanning <b>product discovery, advisory, deployment, and after-sales service</b>
    ◦ AI-enabled touchpoints including chatbots and localized support
• <b>Business Model</b>:
    ◦ Phygital distribution model combining <b>AI-enabled digital platform + village-level offline stores</b>
    ◦ Asset-light approach with <b>franchise-led last-mile distribution</b>
    ◦ Multiple revenue streams across <b>B2C sales, B2B projects, partnerships, franchise fees, and AMC services</b>

<b>Problems</b>
Rural India faces structural inefficiencies in energy access and agri productivity:
• High dependence on <b>firewood, diesel, and unreliable electricity</b>
• Limited access to <b>modern technologies and advisory support</b>
• Fragmented distribution through traditional dealer networks limits penetration

<b>Solutions</b>
A <b>one-stop, full-stack renewable energy platform</b> addressing access, affordability, and adoption:
• <b>Phygital Marketplace</b>: Seamless online + offline distribution network
• <b>AI-led Advisory</b>: Personalized product recommendations and assisted buying
• <b>Last-Mile Reach</b>: Deep rural penetration via trained partners and franchise stores
• <b>Integrated Offering</b>: Solar, biogas, thermal, and green energy products under one platform
• <b>Value-Added Services</b>: Financing support, insurance, and long-term after-sales service

<b>Traction & Impact</b>
• <b>Revenue</b>: INR 5.1 Cr achieved till Feb'25 with ~105% YoY growth
• <b>Advance Orders</b>: INR 2 Cr pipeline
• <b>On-ground Impact (FY20-25)</b>: 1,24,153+ lives impacted; 1,10,000+ women impacted
• 2,070+ tons of CO2 emissions abated
• 66,000+ green jobs created; 900+ acres irrigated via solar

<b>Differentiation</b>
• <b>First-mover advantage</b> in building a <b>renewable energy marketplace with advisory layer</b>
• Strong <b>last-mile rural distribution network</b> vs. e-commerce-led competitors
• Integrated stack combining <b>commerce, financing, service, and impact delivery</b>

<b>Fundraise</b>
• <b>Raising</b>: USD 500K - 1M
• <b>Use of Funds</b>: Expansion, product development (AgriVoltaics), team scale-up, and market expansion

If this aligns with your portfolio focus and does not conflict with it, I’d be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.

For more details about our services: [Website](https://qvscl.com) | [Linkedin]({sender_linkedin})
Looking forward to your response.
"""
        return {
            "subject": f"Strategic Investment Opportunity: Climate-focused Agritech Platform",
            "body": body
        }

    def generate_palak_email(self, lead: dict, sender_name: str = "Palak", sender_linkedin: str = "https://linkedin.com/in/palak"):
        return self.generate_email(lead, sender_name, sender_linkedin)

    def generate_followup(self, lead_name: str, original_content: str, stage: int):
        """Generates a personalized follow-up email with multi-LLM fallback."""
        prompt = f"""
        You are a polite, professional executive assistant. Write a SHORT follow-up email for {lead_name}.
        
        Previous Context:
        {original_content}
        
        Follow-up Stage: {stage} (1=First nudge, 2=Second nudge, 3=Final follow-up)
        
        Guidelines:
        1. Reference the previous email naturally.
        2. Keep it under 3-4 sentences.
        3. Be polite and helpful, not pushy.
        4. If Stage 3, mention this is the final follow-up.
        5. Write ONLY the email body. Use HTML for bolding important parts.
        """
        
        res = self._call_llm(prompt)
        return res if res else "Hi, just following up on my previous email. Let me know if you have any questions!"

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
        
        refined_text = self._call_llm(prompt, max_tokens=2048)
        if not refined_text: return {"subject": subject, "body": body}

        new_subject = subject
        new_body = refined_text
        if "Subject:" in refined_text:
            parts = refined_text.split("\n\n", 1)
            new_subject = parts[0].replace("Subject:", "").strip()
            if len(parts) > 1:
                new_body = parts[1].strip()
        
        return {"subject": new_subject, "body": new_body}

    def detect_intent(self, query: str):
        """
        Query Intent Detection v2: Classifies the user query into functional categories.
        """
        prompt = f"""
        Analyze the user query and classify it into EXACTLY one of the following categories:
        1. SUMMARY: User wants a high-level overview or summary of a lead/document.
        2. EXTRACTION: User wants specific metrics, dates, or data points (e.g., "What is the revenue?").
        3. COMPARISON: User wants to compare two or more leads or documents.
        4. WEB_SEARCH: User is asking for current market data or external info not in the docs.
        5. CHAT: General conversation or follow-up questions.
        
        Query: "{query}"
        
        Return ONLY the category name in uppercase.
        """
        intent = self._call_llm(prompt, max_tokens=20)
        return intent.strip().upper() if intent else "CHAT"

    def web_search_enhanced_query(self, query: str):
        """
        Web-Augmented RAG: Integrates real-time market data into the LLM context.
        """
        # In a real implementation, this would call Serper/Google Search API
        # For now, we simulate the augmentation with a strategic market context prompt.
        market_prompt = f"""
        Provide a real-time market intelligence brief for the following query: "{query}"
        Focus on:
        1. Current funding climate for the relevant sector.
        2. Top 3 competitors or emerging players.
        3. Recent regulatory or technology shifts (2025-2026).
        
        Return ONLY the intelligence brief as a list of bullet points.
        """
        market_intel = self._call_llm(market_prompt, max_tokens=512)
        return market_intel if market_intel else "Market data currently unavailable."

    def analyze_with_citations(self, query: str, context: str):
        """
        Generates an answer with Citation Highlighting enabled.
        """
        prompt = f"""
        Answer the following query based ONLY on the provided context.
        
        RULES:
        1. For every claim you make, you MUST include a citation in the format [Source: X] where X is the document/section name.
        2. If the information is not in the context, state "Information not found in documents."
        3. Use a professional, analyst-style tone.
        
        Context:
        {context}
        
        Query: {query}
        
        Answer:
        """
        return self._call_llm(prompt, max_tokens=1024)

    def classify_reply(self, text: str):
        """Analyzes a lead's reply to determine intent and extract details."""
        prompt = f"""
        Analyze this email reply from a potential investor/client and extract details in JSON format.
        
        CRITICAL RULES:
        1. Identify the new response/reply at the very beginning/top of the text. Ignore any quoted historical thread or original outreach text trailing after it (e.g., descriptions of QVSCL, the climate agritech project, traction, etc.).
        2. If the lead declines the opportunity in the new reply—even in a short sentence like "Pass from us", "Pass for now", "Not interested", "Not within our mandate", "Too early for us", "No thank you"—you MUST classify the intent as "NOT_INTERESTED" and set the sentiment_score between 0 and 20.
        3. Do NOT let the details of the original outreach email (which is positive) confuse you. Focus 100% on the lead's new reply at the top.
        4. CRITICAL — deal_size: Extract the ticket size, investment range, check size, or revenue criteria (MONETARY VALUES ONLY, e.g., '$1M', '$500K-$1M', 'INR 100 cr+', '10-20 Cr') explicitly mentioned in the lead's NEW reply (the top part). Crucially: DO NOT include stage names like 'Series A', 'Series B', 'Seed', or 'Pre-Seed' — only extract numeric monetary values/ranges. If none is mentioned, set null.
         5. CRITICAL — pitch_deck_url: ONLY set if the lead's NEW reply explicitly includes a URL or attachment reference. Do not fabricate or copy from the quoted thread.
        
        REPLY TEXT:
        {text}
        
         JSON STRUCTURE:
         {{
           "intent": "MEETING_REQUESTED" | "INTERESTED" | "NEEDS_MORE_INFO" | "NOT_INTERESTED",
           "deal_size": "ticket size, investment range, or revenue criteria mentioned (MONETARY VALUES ONLY, e.g., '100 cr+', '$1M', '$500K-$1M') or null if not mentioned. Do not include stage names like 'Series A' or 'Series B'.",
           "has_pitch_deck": boolean,
           "pitch_deck_url": null if not explicitly shared by the lead,
           "sentiment_score": integer (0-100),
           "urgency_level": "HIGH" | "MEDIUM" | "LOW",
           "proposed_meeting_date": "If intent is MEETING_REQUESTED, extract the proposed date/time as ISO date if clear (e.g. '2026-06-15T10:00:00'), otherwise null",
           "proposed_meeting_text": "If intent is MEETING_REQUESTED, the exact phrase mentioning the meeting time (e.g. 'Monday ko baat karte hain', 'let's talk next week'), otherwise null",
             "rejection_reason": "A concise 3-8 word summary of the lead's response or rejection reason (e.g. 'Focus on Series B onwards', 'Too early for us', 'Interested, wants to connect', 'Requesting pitch deck', 'Wants meeting next week'). Crucially: DO NOT include greetings (like 'Dear Yashika', 'Hi', 'Hello'), signatures, names, disclaimers, or HTML tags. Keep it very clean and short."
          }}
        """
        result_text = self._call_llm(prompt, max_tokens=512)
        if not result_text: return {"intent": "NOT_INTERESTED"}

        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            try: return json.loads(json_match.group(0))
            except: pass
        return {"intent": "NOT_INTERESTED"}



class LLMService(EmailGenerator):
    pass