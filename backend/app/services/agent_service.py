import logging
import json
from typing import List, Optional
from datetime import datetime
from app.database import get_db_connection
from app.services.llm_services import EmailGenerator
from app.models.lead import add_activity_log

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        self.llm = EmailGenerator()

    def detect_contradictions(self, lead_data: dict, rag_insights: dict) -> List[str]:
        """
        Contradiction Detection: Compares DB metadata with RAG extracted metrics.
        """
        contradictions = []
        
        # 1. Sector Mismatch
        db_sector = (lead_data.get('sector') or '').lower()
        rag_sector = (rag_insights.get('category') or rag_insights.get('type') or '').lower()
        if db_sector and rag_sector and db_sector != rag_sector:
            contradictions.append(f"Sector Mismatch: DB says '{db_sector}', RAG extracted '{rag_sector}'")

        # 2. Revenue Mismatch (Basic heuristic)
        actuals = rag_insights.get('actuals', {})
        if 'revenue' in actuals:
            rag_rev = str(actuals['revenue']).lower()
            db_remarks = (lead_data.get('remarks') or '').lower()
            # Simple check if DB remarks mention a different revenue
            if 'cr' in rag_rev or 'l' in rag_rev:
                # Potential mismatch if DB says pre-revenue but RAG finds cr/l
                if 'pre-revenue' in db_remarks:
                    contradictions.append(f"Revenue Conflict: DB suggests 'Pre-revenue', but RAG found '{actuals['revenue']}'")

        # 3. Funding Stage Conflict
        rag_stage = (rag_insights.get('stage') or '').lower()
        if rag_stage and 'series' in rag_stage:
            if 'seed' in db_remarks:
                contradictions.append(f"Stage Mismatch: DB says 'Seed', but RAG identified '{rag_stage}'")

        return contradictions

    def generate_autonomous_report(self, lead_id: int) -> str:
        """
        Autonomous Report Generation: Creates a comprehensive deep-dive report for a lead.
        """
        conn = get_db_connection()
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s", (lead_id,))
            lead = cur.fetchone()
            if not lead: return "Lead not found."

            rag_advice = lead.get('rag_advice') or "No RAG data available."
            intel = lead.get('rag_intelligence')
            if isinstance(intel, str): intel = json.loads(intel)
            
            prompt = f"""
            Generate a comprehensive Autonomous Investment Report for: {lead['company_name']}
            
            LEAD DATA:
            Sector: {lead['sector']}
            Role: {lead['designation']}
            Persona: {lead['persona']}
            
            RAG INSIGHTS:
            {rag_advice}
            
            STRUCTURE:
            1. Executive Summary (2-3 sentences)
            2. Business Model & Strategy (Detailed analysis)
            3. Key Metrics (Extracted from documents)
            4. Risks & Red Flags (Critical evaluation)
            5. Final Verdict & Recommendation
            
            Rules:
            - Use professional analyst tone.
            - Format with Markdown (headers, bullet points).
            - Include a 'Source Credibility' score (0-100).
            """
            
            report = self.llm._call_llm(prompt, max_tokens=3000)
            
            # Log activity
            add_activity_log(lead_id, "REPORT_GENERATED", "Autonomous AI Report generated successfully", "agent")
            
            return report
        finally:
            cur.close()
            conn.close()

    async def run_lead_pipeline(self, lead_id: int):
        """
        Agentic Workflow Automation: Automated multi-step analysis pipeline.
        1. Enrichment -> 2. RAG Analysis -> 3. Contradiction Check -> 4. Scoring -> 5. Draft
        """
        logger.info(f"Starting agentic pipeline for lead {lead_id}")
        
        # This would call existing intelligence functions sequentially
        # and handle state transitions.
        # For now, it acts as the orchestrator.
        pass
