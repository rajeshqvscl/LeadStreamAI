from fastapi import APIRouter, Header, UploadFile, File, HTTPException
from pydantic import BaseModel
import traceback
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import base64

from app.models.lead import get_lead_by_id
from app.models.draft import insert_draft
from app.database import get_db_connection
from app.services.llm_services import EmailGenerator
from app.services.vision_service import analyze_template_screenshot
import psycopg2.extras
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

# --- REDIS CACHE INITIALIZATION ---
import os
redis_client = None
redis_available = False

try:
    import redis
    REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
    redis_client = redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )
    redis_client.ping()
    redis_available = True
    logger.info(f"SUCCESS: Connected to Redis Cache inside drafts.py at {REDIS_URL.split('@')[-1]}")
except Exception as re_err:
    logger.warning(f"NOTICE: Redis is not active inside drafts.py. Falling back to direct database. Error: {re_err}")
    redis_client = None
    redis_available = False

def invalidate_pending_drafts_cache(user_id: str = "*"):
    if redis_available and redis_client:
        try:
            pattern = f"pending_drafts:{user_id}:*"
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
                logger.info(f"SUCCESS: Invalidated cache keys for pattern: {pattern}")
        except Exception as ie:
            logger.error(f"Failed to invalidate pending drafts cache: {ie}")

# Guaranteed self-healing database update at module load/hot-reload time
try:
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Yashika AI Tech Template
    latest_description = "AI-Powered Hiring Infrastructure Platform fundraising draft ($1M)"
    latest_content = """Subject: AI-Powered Hiring Infrastructure Platform Company | 100K+ Recruiters | 250+ Companies |

Dear {{First Name}},

I hope you're doing well.

I'm {{Sender First Name}} from QVSCL (Gurugram), a strategic advisory firm working with high-growth early-stage ventures. We are currently raising a round for a platform building a **vertical AI-powered hiring intelligence layer**, combining AI agents, recruitment workflows, and trust-based verification infrastructure.

**Business Overview**

**Headquarters:** Singapore (with India as a 100% owned subsidiary and a US joint venture)

**Founded:** By industry leaders with 20+ years of experience across HR, fintech, and enterprise technology

**Focus:** Building a unified hiring infrastructure platform that automates and optimizes end-to-end recruitment workflows - spanning sourcing, screening, evaluation, and background verification

**Platform Offering:** A full-stack hiring infrastructure platform integrating applicant tracking, multi-channel sourcing, AI-driven screening, and native background verification into a single system

**Technology:** AI-powered vertical agents enabling sourcing, scheduling, interviewing, and verification workflows, supported by a proprietary trust graph that improves candidate matching and reduces fraud over time

**Revenue Model:** Enterprise SaaS with multi-layered monetization across hiring workflows, verification services, and AI-driven automation modules, enabling scalable and recurring revenue streams

**Core Differentiation:** Unlike fragmented HR tech stacks, the platform functions as a **system of intelligence for hiring** - combining workflows, data, and verification into a unified infrastructure layer that improves decision-making over time. Positioned alongside global AI hiring platforms, with differentiated focus on integrated trust infrastructure and verification layers.

*Designed to become the underlying infrastructure layer for hiring in an era of AI-generated talent and rising trust deficits*

**Industry Overview**

Hiring at scale remains highly inefficient despite large market size:

• 3.6M job vacancies are posted monthly in India, but only 2.1M hires are completed
• 1.5M workforce gap leading to significant unrealized economic output
• 80% of employers face talent shortages
• Hiring processes remain largely manual and fragmented

**Market Opportunity:**

• Global Hiring & Recruitment Tech TAM: $150B+
• Rapid shift toward AI-driven automation, trust, and verification layers (35-45% CAGR)

**Problems**

**HR & Recruiter Challenges**

• 180 applications per hire leading to massive screening overload
• Recruiters managing significantly higher workloads without increased team size
• 57% of time spent on repetitive "data janitorial" tasks

**Process Inefficiencies**

• Fragmented workflows across 20+ tools (ATS, sourcing, BGV, onboarding)
• Manual data handling and poor system integrations
• Long hiring cycles (average 44 days to fill roles)

**Trust & Quality Issues**

• 70% resumes contain inaccuracies
• AI-generated and unverified profiles flooding pipelines
• High attrition and hiring inefficiencies due to poor matching

**Solutions**

• **AI Hiring Co-Pilot:** Automates sourcing, screening, and evaluation
• **Unified Infrastructure:** One system across ATS, sourcing, and verification
• **Trust Layer:** Proprietary graph improving match quality and fraud detection
• **Background Verification:** Native BGV system with 20+ checks across identity, employment, education, and criminal records
• **Workflow Automation:** Eliminates manual processes, reducing HR workload and improving hiring efficiency
• **Scalable Architecture:** APIs and integrations with HRMS/ATS systems enabling enterprise-grade deployment

**Validations & Traction**

• 100K+ companies onboarded on the platform
• 250+ enterprise customers across 50+ industries
• Currently in advanced discussions for potential onboarding across multiple enterprise accounts
• Rapid enterprise adoption across India and international markets, with strong demand from US-based customers
• 60% of current and projected revenue driven by US market demand
• 94% customer retention rate

**Operational Impact:**

• Near real-time hiring cycles (2-3 days vs 44 days industry average)
• Background verification TAT reduced from 15 days to 2 days
• 40%+ reduction in HR operational workload

**Fundraise**

• Total capital raised in previous rounds: $3M
• Currently raising: $1M - $3M

Happy to walk you through a quick live product demo showcasing the platform in action

If this aligns with your portfolio focus and does not conflict with it, I'd be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.

For more details about our services:

[Website](https://qvscl.com) | [Linkedin](https://www.linkedin.com/company/qvscl/)

Looking forward to your response.

SIG_START
--
Thanks & Regards,

***{{Sender Name}}***
{{Sender Title}}
[LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}

Important: This message and its attachments are intended only for the addressee and may contain legally privileged and/or confidential information. If you are not the intended recipient, you are hereby notified that you must not use, disseminate, or copy this material in any form, or take any action based upon it. If you have received this message by error, please immediately delete it and its attachments and notify the sender at QV Strategic Consulting LLP by electronic mail message reply. Thank you.
SIG_END"""

    cur.execute("SELECT id FROM prompts WHERE name = 'yashika_draft_ai_tech'")
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE prompts SET content = %s, description = %s WHERE name = 'yashika_draft_ai_tech'",
            (latest_content, latest_description)
        )
    else:
        cur.execute(
            "INSERT INTO prompts (name, description, content, prompt_type) VALUES ('yashika_draft_ai_tech', %s, %s, 'CUSTOM_DRAFT')",
            (latest_description, latest_content)
        )
    conn.commit()

    # 2. Ayush Sir Hospital Template
    hospital_description = "Integrated Multi-Site Hospital Platform in Eastern Uttar Pradesh ($240 Cr EV)"
    hospital_content = """Subject: Strategic Investment Opportunity – Integrated Multi-Site Hospital Platform in Eastern Uttar Pradesh

Dear {{First Name}},

Greetings for the day.

I hope this message finds you well.

My name is {{Sender First Name}}, an Investment Banker based out of Gurugram, representing QV Strategic Consulting LLP, an Investment Banking firm focused on strategic transactions and growth capital advisory across high-potential sectors in India.

We are currently advising on a **strategic investment / acquisition opportunity** for a rapidly growing **hospitals operating across Eastern Uttar Pradesh, one of India's largest yet significantly underserved healthcare markets**.

This opportunity combines:

• **Strong existing profitability**
• **Embedded operating leverage**
• **Asset-backed downside protection**
• **Infrastructure-ready scalability**
• **Attractive cash-flow characteristics**
• **Significant regional healthcare demand tailwinds**
• **Healthy EBITDA Margins**
• **PAT Positive Operations**

At a time when institutional investors and strategic healthcare operators are actively seeking scalable regional healthcare platforms, this business offers a differentiated opportunity to acquire a profitable and operationally established healthcare ecosystem ahead of its next phase of expansion.

**Investment Snapshot**

| Particulars | Current Metrics |
| --- | --- |
| Net Revenue | ~₹49.2 Cr |
| EBITDA | ~₹16.8 Cr |
| EBITDA Margin | ~34.2% |
| PAT | ~₹8.4 Cr |
| Installed Capacity | 225 Beds |
| ARPOB / RPOB | ~₹26,000 |
| Average Length of Stay | 3.8 Days |
| Blended Occupancy | ~28.3% |

**Why This Opportunity Stands Out:**

**1. Rare Combination of High Margins + Underutilized Capacity**

The platform is already generating **~34.2% EBITDA margins** despite occupancy levels remaining **significantly below mature hospital-chain benchmarks**.

This is particularly important because current profitability is being generated *before* operational maturity.

The business currently operates at only **~28.3% blended occupancy across 225 installed beds**, creating substantial embedded operating leverage potential as utilization scales.

Unlike many healthcare businesses where profitability is already fully optimized, this platform offers investors the ability to participate in future EBITDA expansion through:

• Occupancy ramp-up
• Clinician additions
• Improved referral conversion
• Diagnostics attachment
• Better throughput utilization
• Commercial optimization

while leveraging an already operational infrastructure base.

**2. Strong Monetization Metrics Already Achieved**

Despite relatively low occupancy, the platform has already achieved **ARPOB levels of approximately ₹26,000**, indicating strong monetization quality and healthy case-mix realization for the region.

This is a key indicator because it demonstrates that the current opportunity is not dependent on aggressive pricing assumptions - monetization strength already exists at current throughput levels.

**3. Attractive Revenue Quality & Cash Conversion**

The business benefits from a highly favorable payer mix:

| Revenue Mix | Contribution |
| --- | --- |
| Cash | ~58.3% |
| Corporate | ~39.0% |
| TPA | Only ~2.7% |

This significantly **reduces**:

• Receivable cycles
• Insurance adjudication delays
• Working capital inefficiencies
• Collection stress

and supports stronger cash generation compared to hospital businesses with heavier TPA dependence.

In addition, revenue remains balanced between:

• **IPD Revenue:** ~50.7%
• **OPD + Daycare Revenue:** ~49.3%

creating diversified patient monetization and recurring engagement opportunities.

**4. Diversified Clinical Platform**

The platform has established a broad tertiary-care ecosystem across multiple specialties including:

• Cardiology
• Nephrology
• Neuro Sciences
• Orthopedics
• Gynecology
• Pediatrics
• Physician Medicine

Importantly, the business is not dependent on a single specialty vertical, improving resilience and earnings visibility.

The **top 8 specialties contribute ~85.5% of specialty revenue**, providing a balanced mix of bread-and-butter healthcare demand along with higher-acuity procedures.

**5. Infrastructure-Ready Growth Platform**

A significant portion of the infrastructure and operating ecosystem is already in place.

Management indicates that only **~₹5 Cr** of selective readiness and productivity capex may be required to support:

• Equipment refresh
• Throughput enhancement
• Facility activation
• Productivity improvement
• Selective expansion initiatives

This materially lowers execution and capital deployment risk relative to greenfield hospital expansion strategies.

**6. Strong Historical Momentum**

| Metric | Growth |
| --- | --- |
| Core Hospital EBITDA Growth | ~9.9% |
| Occupancy Growth | ~14.3% |
| ARPOB Growth | ~4.0% |

The simultaneous improvement in occupancy and monetization highlights strengthening operational quality.

**7. Asset-Backed Downside Protection**

The transaction includes a flagship owned hospital campus providing meaningful underlying hard-asset value within the overall transaction structure.

This creates an additional layer of downside support while preserving upside from future operating scale and institutionalization.

**8. Attractive Industry Positioning & Regional Tailwinds**

Eastern Uttar Pradesh remains significantly underserved in organized tertiary and super-specialty healthcare penetration relative to metropolitan India.

Simultaneously, broader Indian healthcare sector dynamics remain highly favorable:

• Increasing formalization of healthcare delivery
• Rising patient preference for organized providers
• Strong Tier-2 and Tier-3 healthcare demand growth
• Limited availability of scalable regional healthcare assets
• Expanding institutional capital participation in healthcare

These factors continue to support premium valuations for high-quality regional healthcare platforms with scalable infrastructure and operating visibility.

**9. Indicative Transaction Overview**

The proposed transaction perimeter includes:

• Operating hospital business
• Owned primary hospital campus
• Secondary leased campus operations

Currently, the transaction is being discussed at an indicative enterprise valuation of approximately **₹240 Cr** depending on structure and diligence outcomes.

We believe this opportunity represents a compelling combination of:

• **~34.2% existing EBITDA margins**
• **Strong current cash-flow profile**
• **Strong existing profitability**
• **Embedded operating leverage from underutilized capacity**
• **Infrastructure-ready scalability**
• **Regional healthcare demand expansion**
• **Strong monetization characteristics**
• **Asset-backed downside support**

At QV Strategic Consulting LLP, we specialize in facilitating **high-potential investment opportunities for long-term capital partners**. I would be happy to schedule a 30-minute virtual call to discuss this opportunity further.

I have attached the **QV Strategic Consulting business profile** and **Investment Teaser** for your reference.

SIG_START
--
Thanks & Regards,

***{{Sender Name}}***
{{Sender Title}}
[Website](https://www.qvscl.com) | [LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}

![Investment Opportunity Banner]([[BACKEND_URL]]/assets/PHOTO-2026-05-25-10-33-35.jpg)

<strong>Strictly Private and Confidential.</strong>

The information contained in this email is confidential, may be legally privileged, may constitute inside information and is intended solely and exclusively for the use of the intended addressee and any others who have been specifically authorized to receive it. Quantum Value Strategic Consulting does not provide legal, accounting or tax advice. Any statement in this email (including any attachments) regarding legal, accounting or tax matters was written in connection with the explanation of the matters described herein and was not intended or written to be relied upon by any person. Unauthorized dissemination, distribution, disclosure or other use of the contents of this email is strictly prohibited and may be unlawful. If you have received this email in error, please notify us immediately by return email and destroy this message and all copies thereof, including any attachments.
SIG_END"""

    # FORCE UPDATE
    cur.execute(
        "UPDATE prompts SET content = %s, description = %s WHERE name = 'ayush_sir_hospital_draft'",
        (hospital_content, hospital_description)
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO prompts (name, description, content, prompt_type) VALUES ('ayush_sir_hospital_draft', %s, %s, 'CUSTOM_DRAFT')",
            (hospital_description, hospital_content)
        )
    conn.commit()

    # 3. Palak Mam Corporate Advisory Template
    palak_corp_description = "Corporate Advisory / Equity Fund Raising Services — QVSCL Introduction"
    palak_corp_content = """Subject: Corporate Advisory/ Equity Fund Raising Services.

Dear {{First Name}},

Greetings from QVSCL!

I hope you're doing well.

I'm excited to introduce QV Strategic Consulting, your trusted partner for driving sustainable capital growth. With extensive experience across diverse industries, we combine strategic expertise, innovation, and hands-on execution to help businesses achieve their goals.

<strong>Key Areas of Expertise:</strong>

• Preparation to IPO – Standardizing information systems, due diligence, information memorandum, and more.
• Fund Raising – Equity and debt financing solutions tailored to your needs.
• Board Advisory – Strategic guidance to enhance governance and decision-making.
• Implementing Partner – Strengthening management teams for seamless execution.
• Fostering Strategic Partnerships & Alliances – Facilitating joint ventures, mergers, and acquisitions.
• Strategic Business Planning – Crafting actionable roadmaps for long-term success.

To learn more about how we can support your growth ambitions, see our [website](https://qvscl.com) or connect with us on [LinkedIn](https://www.linkedin.com/company/qvscl/).

We'd love to schedule a virtual meeting at your convenience to explore potential collaboration. Kindly share your availability, and we'll coordinate a suitable time.

Attached, you'll find our company profile for your reference. Looking forward to connecting!

SIG_START
--
Thanks & Regards,

***{{Sender Name}}***
{{Sender Title}}
[Website](https://www.qvscl.com) | [LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}

<strong>Strictly Private and Confidential.</strong>

The information contained in this email is confidential, may be legally privileged, may constitute inside information and is intended solely and exclusively for the use of the intended addressee and any others who have been specifically authorized to receive it. Quantum Value Strategic Consulting does not provide legal, accounting or tax advice. Any statement in this email (including any attachments) regarding legal, accounting or tax matters was written in connection with the explanation of the matters described herein and was not intended or written to be relied upon by any person. Unauthorized dissemination, distribution, disclosure or other use of the contents of this email is strictly prohibited and may be unlawful. If you have received this email in error, please notify us immediately by return email and destroy this message and all copies thereof, including any attachments.
SIG_END"""

    # FORCE UPDATE
    cur.execute(
        "UPDATE prompts SET content = %s, description = %s WHERE name = 'palak_mam_corporate_advisory'",
        (palak_corp_content, palak_corp_description)
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO prompts (name, description, content, prompt_type) VALUES ('palak_mam_corporate_advisory', %s, %s, 'CUSTOM_DRAFT')",
            (palak_corp_description, palak_corp_content)
        )
    conn.commit()

    # 4. Kajal Mam Health Ecosystem Template
    kajal_ecosystem_description = "AI-Enabled Preventive Health Ecosystem Platform ($1M Seed)"
    kajal_ecosystem_content = """Subject: India's AI-Enabled Preventive Health Ecosystem Platform | ₹2.6Cr ARR | 300+ Labs

Dear {{First Name}},

I hope you're doing well.

I'm Kajal from QVSCL (Gurugram), a strategic advisory firm working with high-growth early-stage ventures. We are currently raising a **Seed Round** for a platform building India's preventive health ecosystem layer, combining diagnostics infrastructure, **genomics**, AI-driven insights, and continuous health monitoring.

**Business Overview**

**Founded:** 2024 by an undergraduate student from IIT Madras

**Focus:** Building a preventive health ecosystem platform that digitizes India's fragmented diagnostics sector. The platform integrates diagnostics, **genomic insights**, logistics, and institutional demand through a unified B2B2C marketplace and SaaS-enabled ecosystem.

**Platform Offering:** Enables users to compare diagnostic tests, book home sample collections, access reports, manage health records, and leverage **genomic profiling for personalized preventive care** through a single platform.

**Technology:** AI-powered platform featuring an AI test recommendation engine, AI health monitoring engine, AI chatbot & health assistant, and **genomics-enabled risk assessment layer**, along with real-time lab geo-matching and SaaS-based CRM dashboards for labs.

**Revenue Model:** Built on multi-layered revenue streams combining transaction margins on diagnostic bookings, **genomics-based premium offerings**, and a preventive subscription layer, enabling scalable and diversified revenue generation.

**Social Impact:** By digitizing smaller labs, integrating **genomic intelligence**, and improving access to diagnostics, the platform enhances healthcare accessibility and advances preventive health awareness.

**Industry Overview**

India's diagnostics sector is large but structurally fragmented.

• Delhi NCR Diagnostics Market: ₹9,100 Cr annually
• Preventive Monitoring Opportunity: ₹3,150 Cr annually
• Emerging **genomics and personalized medicine market** adding a high-growth layer to preventive healthcare
• Most diagnostic testing still begins only after symptoms appear
• Over 90% of diagnostic labs lack digital visibility
• Adoption of preventive and personalized healthcare is still in early stages

**Problems**

**Patient Challenges**

• No unified platform to manage diagnostic tests, health records, and **genomic data**
• Diagnostics largely begin after symptoms appear
• No structured preventive or **genomics-driven health programs**
• Difficulty comparing prices, labs, and service quality

**Lab Challenges**

• Majority of labs have no digital discovery or booking system
• Heavy reliance on walk-ins
• Underutilized capacity
• Limited participation in **advanced diagnostics like genomics**

**System-Level Challenges**

• No unified diagnostic and **genomics-integrated infrastructure layer**
• Preventive healthcare programs remain unstructured
• Limited coordination across labs, logistics, and institutions
• Absence of a comprehensive ecosystem integrating diagnostics, genomics, and continuous monitoring

**Solutions**

• **Diagnostics Network:** 300+ partner labs integrated
• **Genomics Integration:** Enabling **genetic testing, risk profiling, and personalized preventive insights**
• **Home Collection & Logistics:** 24x7 phlebotomy network
• **Fast Booking:** Under 30 minutes via app/web
• **Preventive Monitoring:** Structured annual health baseline + **genomics-informed monitoring programs**
• **Institutional Integrations:** Corporates, schools, RWAs
• **Technology & SaaS Layer:** Diagnostics aggregation + lab CRM tools
• **Data Continuity:** Unified diagnostic + **genomic health records** for longitudinal tracking
• **Ecosystem Approach:** Integrating diagnostics, genomics, logistics, and institutions into a unified preventive health layer

**Validations & Traction**

• Launched: September 2025
• Active Lab Network: 300+ Labs
• Orders Completed: 7,000+
• Revenue Generated: ₹89L+
• ARR: ₹2.58 Cr
• Fully operational across Delhi NCR

**Investment Details**

**Fundraise:** **Seed** Round of $1 million

**Utilization Plan:**
• Technology and product development (including **genomics capabilities**)
• Expansion of diagnostic & genomics partner network
• Customer acquisition & market expansion
• Corporate and institutional partnerships
• Operational and compliance infrastructure

If this aligns with your portfolio focus and does not conflict with it, I'd be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.

For more details about our services:
[Website](https://qvscl.com) | [Linkedin]({{Sender LinkedIn}})

Looking forward to your response.

SIG_START
[Click here to unsubscribe](https://qvscl.com/unsubscribe)

--
Thanks & Regards,

***{{Sender Name}}***
{{Sender Title}}
[LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}
<img src="[[BACKEND_URL]]/assets/kajal.png" style="width: 150px; height: auto; display: block; margin-top: 10px;" />

Important: This message and its attachments are intended only for the addressee and may contain legally privileged and/or confidential information. If you are not the intended recipient, you are hereby notified that you must not use, disseminate, or copy this material in any form, or take any action based upon it. If you have received this message by error, please immediately delete it and its attachments and notify the sender at Quantum Value Strategic Consulting LLP by electronic mail message reply. Thank you.
SIG_END

<div style="text-align: center; margin-top: 25px; font-weight: bold; color: #444; font-size: 12px; letter-spacing: 1.5px;">CONFIDENTIAL | FOR PRIVATE CIRCULATION ONLY</div>"""

    cur.execute(
        "UPDATE prompts SET content = %s, description = %s WHERE name = 'kajal_mam_health_ecosystem'",
        (kajal_ecosystem_content, kajal_ecosystem_description)
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO prompts (name, description, content, prompt_type, owner_username) VALUES ('kajal_mam_health_ecosystem', %s, %s, 'CUSTOM_DRAFT', 'kajal')",
            (kajal_ecosystem_description, kajal_ecosystem_content)
        )
    conn.commit()

    # 5. Kajal Mam QVSCL Introduction Template
    kajal_qvscl_description = "QVSCL Capital & Growth Solutions for Portfolio Companies"
    kajal_qvscl_content = """Subject: QVSCL: Capital & Growth Solutions for Portfolio Companies

Dear {{First Name}},

I am reaching out to introduce QVSCL, a strategic advisory and capital-raising firm focused on helping businesses scale, optimize operations, and access growth capital.

We work closely with founders, portfolio companies, family offices, and investors across sectors including Agritech, Healthcare, Deep Tech, Retail, Engineering, and Automobiles.

**Our key areas of expertise include:**

• Secondary fundraising for portfolio companies
• Strategic partnerships, joint ventures, mergers & acquisitions
• Business strategy and advisory, including business plans, competitor analysis, benchmarking, and financial modeling
• Succession planning and family office structuring for family-owned businesses
• Turnaround management, organizational restructuring, and profitability optimization
• Advanced Data Analytics, Data Science, and HR Dashboard solutions

We would welcome the opportunity to explore how QVSCL can support your portfolio companies and strategic initiatives.

Additionally, if you could share your investment thesis, sector focus, and preferred investment stage, we would be pleased to share relevant deal flow opportunities aligned with your mandate.

Please find attached the QVSCL company profile and founder profile for your reference.

**For more information:**
[Website](https://qvscl.com/) | [LinkedIn](https://www.linkedin.com/company/qvscl/)

I would be happy to schedule a brief call at your convenience and discuss potential areas of collaboration.

Looking forward to connecting."""

    cur.execute(
        "UPDATE prompts SET content = %s, description = %s WHERE name = 'kajal_mam_qvscl_intro'",
        (kajal_qvscl_content, kajal_qvscl_description)
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO prompts (name, description, content, prompt_type, owner_username) VALUES ('kajal_mam_qvscl_intro', %s, %s, 'CUSTOM_DRAFT', 'kajal')",
            (kajal_qvscl_description, kajal_qvscl_content)
        )
    conn.commit()

    # 6. Palak Mam M&A and Fundraising Template
    palak_mna_description = "Supporting Growth Through M&A and Fundraising"
    palak_mna_content = """Subject: Supporting Growth Through M&A and Fundraising.

Dear {{First Name}},

Greetings from QVSCL.

We're pleased to introduce QV Strategic Consulting, your trusted partner for driving sustainable growth and value creation. With extensive experience across diverse industries, we help businesses achieve their growth objectives through fundraising, mergers & acquisitions, and strategic partnerships.

In M&A Advisory, we support:
• Acquisitions to expand capabilities, market presence, or product offerings
• Strategic mergers, joint ventures, and partnerships
• Target identification, valuation, due diligence, negotiation, and transaction execution

In Fundraising Advisory we help with:
• Equity fundraising from VC, PE, Family Offices, and Strategic Investors
• Debt fundraising for growth, working capital, and expansion requirements

If this aligns with your needs, we would be glad to connect and discuss how we can support your strategic objectives. Could we schedule a short video call at your convenience?

Please find our Company Profile attached.

Looking forward to connecting."""

    palak_mna_followup1 = """Dear {{First Name}},

I wanted to follow up on my previous email regarding QV Strategic Consulting's M&A and fundraising advisory services.

I thought it would be worthwhile to connect and understand whether any such initiatives are currently being considered within your organization.

Would you be available for a brief 15-minute discussion sometime in this week or next week?

Looking forward to hearing from you.

Thanks and regards,
Palak"""

    cur.execute(
        "UPDATE prompts SET content = %s, description = %s, followup_1 = %s WHERE name = 'palak_mam_mna_fundraising'",
        (palak_mna_content, palak_mna_description, palak_mna_followup1)
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO prompts (name, description, content, prompt_type, owner_username, followup_1) VALUES ('palak_mam_mna_fundraising', %s, %s, 'CUSTOM_DRAFT', 'palak', %s)",
            (palak_mna_description, palak_mna_content, palak_mna_followup1)
        )
    conn.commit()

    cur.close()
    conn.close()
    logger.info("🚀 Startup templates creation/verification completed successfully!")
except Exception as db_err:
    logger.error(f"⚠️ Startup template creation failed: {db_err}")

def normalize_user_id(user_id: Optional[str]) -> str:
    """Normalizes the user ID from the header to a valid numeric database ID string.
    Handles 'admin' or string usernames by resolving them to their numeric database ID.
    """
    if not user_id or user_id.strip() == "":
        return "1"
    
    u_str = str(user_id).strip()
    if u_str.lower() == "admin":
        return "1"
    
    if u_str.isdigit():
        return u_str
        
    # If not digits, it's likely a username (e.g. "test"). Resolve to numeric ID.
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1", (u_str, u_str))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return str(row[0])
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error resolving user_id for '{u_str}': {e}")
        
    return "1" # Fallback to admin/system if resolution fails


def check_daily_email_limit(user_id: Optional[str], batch_size: int = 1) -> bool:
    """Returns True if the user has not exceeded their daily limit of 2000 sent emails."""
    uid = normalize_user_id(user_id)
    is_admin = (str(user_id or '').lower() == 'admin')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if is_admin:
            cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'SENT' AND updated_at >= NOW() - INTERVAL '1 day'")
        elif uid:
            cur.execute("SELECT COUNT(*) FROM leads_raw WHERE user_id = %s AND email_status = 'SENT' AND updated_at >= NOW() - INTERVAL '1 day'", (uid,))
        else:
            cur.execute("SELECT COUNT(*) FROM leads_raw WHERE user_id IS NULL AND email_status = 'SENT' AND updated_at >= NOW() - INTERVAL '1 day'")
        
        sent_today = cur.fetchone()[0] or 0
        return (sent_today + batch_size) <= 2000
    except Exception as e:
        logger.error(f"Error checking email limit: {e}")
        return True # Default to True to avoid blocking during transient DB errors
    finally:
        cur.close()
        conn.close()

_INLINED_IMAGE_CACHE = {}

def markdown_to_html(text):
    import re
    # Normalize newlines
    text = text.replace("\r\n", "\n")
    # 1. Strip technical markers
    text = text.replace("SIG_START", "").replace("SIG_END", "").replace("[[SIG_PLACEHOLDER]]", "")
    # 1a. Resolve [[BACKEND_URL]] placeholder so images work in send flow
    backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    text = text.replace("[[BACKEND_URL]]", backend_url)
    
    # Convert known asset images to inline base64 data URIs for reliable rendering in email clients
    def _inline_img(m):
        tag = m.group(0)
        src_m = re.search(r'src="([^"]+)"', tag)
        if not src_m:
            return tag
        src = src_m.group(1)
        known = {"PHOTO-2026-05-25-10-33-35.jpg": "image/jpeg", "kajal.png": "image/png"}
        for img_name, mime_type in known.items():
            if img_name in src:
                if img_name in _INLINED_IMAGE_CACHE:
                    new_src = _INLINED_IMAGE_CACHE[img_name]
                    return tag.replace(f'src="{src}"', f'src="{new_src}"')
                img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", img_name)
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode()
                    new_src = f"data:{mime_type};base64,{b64_data}"
                    _INLINED_IMAGE_CACHE[img_name] = new_src
                    return tag.replace(f'src="{src}"', f'src="{new_src}"')
        return tag

    def _inline_md_img(m):
        alt_text = m.group(1)
        src = m.group(2)
        known = {"PHOTO-2026-05-25-10-33-35.jpg": "image/jpeg", "kajal.png": "image/png"}
        for img_name, mime_type in known.items():
            if img_name in src:
                if img_name in _INLINED_IMAGE_CACHE:
                    new_src = _INLINED_IMAGE_CACHE[img_name]
                    return f'<div style="width: 100%; margin-top: 25px; margin-bottom: 25px;"><img src="{new_src}" alt="{alt_text}" style="width: 100%; height: auto; display: block;" /></div>'
                img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", img_name)
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode()
                    new_src = f"data:{mime_type};base64,{b64_data}"
                    _INLINED_IMAGE_CACHE[img_name] = new_src
                    return f'<div style="width: 100%; margin-top: 25px; margin-bottom: 25px;"><img src="{new_src}" alt="{alt_text}" style="width: 100%; height: auto; display: block;" /></div>'
        return m.group(0)
    
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', _inline_md_img, text)
    text = re.sub(r'<img[^>]+>', _inline_img, text, flags=re.DOTALL | re.IGNORECASE)
    # 1.5 Handle Global Bolding (catch any remaining **stars**)
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # 2. Handle Links (Markdown style [Text](URL))
    # Using a more specific regex to avoid catching already-converted HTML tags
    text = re.sub(r'(?<!href=")(?<!src=")\[(.*?)\]\((.*?)\)', r'<a href="\2" style="color: #3b82f6; text-decoration: underline; font-weight: 600;">\1</a>', text)
    
    # 3. Smart Signature Styling (Grey & Italic)
    signature_html = ""
    sig_start_marker = "--"
    
    # Only treat standalone "--" (on its own line, not inside table separators) as sig marker
    sig_split_marker = None
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "--" or stripped == "---" or stripped == "—":
            sig_split_marker = stripped
            sig_line_idx = i
            break
    
    if sig_split_marker is not None:
        all_lines = text.split("\n")
        main_text = "\n".join(all_lines[:sig_line_idx]).rstrip("\n")
        raw_sig = sig_split_marker + "\n" + "\n".join(all_lines[sig_line_idx+1:])
        
        # Style the signature block line-by-line
        sig_lines = raw_sig.strip().split("\n")
        formatted_sig_lines = []
        for line in sig_lines:
            line = line.strip()
            if not line:
                formatted_sig_lines.append('<div style="height: 3px;"></div>')
                continue
                
            disclaimer_text = "Important: This message and its attachments"
            is_legal = disclaimer_text in line or "quantum value strategic consulting" in line.lower() or "unauthorized dissemination" in line.lower()
            is_strictly_private = "strictly private" in line.lower()
            
            if is_legal and not is_strictly_private:
                # Standard legal disclaimer: tiny and grey
                line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                line = f'<span style="font-size: 10px; color: #999; font-style: normal; line-height: 1.2; display: block; margin-top: 10px; border-top: 1px solid #eee; padding-top: 10px;">{line}</span>'
            elif is_strictly_private:
                # Premium Hospital Disclaimer: Bold, prominent, and full-size
                line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                # Ensure "Strictly Private" itself is bolded if not already
                if "<strong>" not in line and "strictly private" in line.lower():
                     line = re.sub(r"(?i)(strictly private and confidential)", r"<strong>\1</strong>", line)
                line = f'<div style="font-size: 13px; color: #444; font-weight: normal; line-height: 1.4; display: block; margin-top: 15px; border-top: 1px solid #ddd; padding-top: 10px;">{line}</div>'
            elif "<div" in line or "<img" in line:
                # Keep raw HTML as-is (like our banner)
                pass
            else:
                # Handle names/titles in signature (bold them if they are in ***)
                line = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong>\1</strong>', line)
                line = f'<span style="color: #666; font-style: italic; display: block; margin-bottom: 0px; font-size: 13px;">{line}</span>'
            
            formatted_sig_lines.append(line)
        
        signature_html = '<div style="margin-top: 4px; border-top: 1px solid #f0f0f0; padding-top: 6px; line-height: 1.4;">' + "".join(formatted_sig_lines) + '</div>'
        text = main_text.rstrip() + "\n\n[[SIG_BLOCK_PLACEHOLDER]]"

    # 4. Handle remaining keywords if they weren't in markdown format
    if "Website" in text and "<a" not in text:
        text = text.replace("Website", '<a href="https://qvscl.com" style="color: #0066cc; text-decoration: underline;">Website</a>')
    
    # Skip "Click here to unsubscribe" conversion — `inject_signature` already
    # adds a proper unsubscribe link, and a plain-text replace would nest it inside
    # the existing <a> tag, creating duplicate unsubscribe links.

    # 5. Standard Markdown
    text = re.sub(r'<b>(.*?)</b>', r'__BOLD__\1__BOLD__', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = text.replace('__BOLD__', '<b>')

    # 5. Paragraph splitting with EXACT Spacing
    paragraphs = text.split("\n\n")
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p: continue
        
        if "[[SIG_BLOCK_PLACEHOLDER]]" in p:
            html_parts.append(signature_html)
            continue
        
        lines = p.split("\n")
        # Bullet points with exact Indentation
        if any(re.match(r'^\s*[◦◦]\s+', l) or re.match(r'^\s{4,}[•\-\*]\s+', l) for l in lines):
            list_html = "<ul style='margin-top: 0; margin-bottom: 12px; padding-left: 50px; list-style-type: circle;'>"
            for l in lines:
                l_strip = l.strip()
                content = re.sub(r'^\s*[◦◦•\-\*]\s+', '', l_strip)
                list_html += f"<li style='margin-bottom: 4px; line-height: 1.6; font-family: Arial, sans-serif;'>{content}</li>"
            list_html += "</ul>"
            html_parts.append(list_html)
        elif any(re.match(r'^\s*[\*\-•]\s+', l) for l in lines):
            list_html = "<ul style='margin-top: 0; margin-bottom: 15px; padding-left: 35px; list-style-type: disc;'>"
            for l in lines:
                l_strip = l.strip()
                match = re.match(r'^[\*\-•]\s+(.*)', l_strip)
                if match:
                    content = match.group(1)
                    list_html += f"<li style='margin-bottom: 6px; line-height: 1.6; font-family: Arial, sans-serif;'>{content}</li>"
                else:
                    list_html += f" {l_strip}"
            list_html += "</ul>"
            html_parts.append(list_html)
        else:
            # Check if this is a markdown table
            lines = p.split("\n")
            if len(lines) >= 2 and all(l.strip().startswith("|") and l.strip().endswith("|") for l in lines):
                table_html = "<table style='width:100%;border-collapse:collapse;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;'>"
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    cells = [c.strip() for c in line.split("|")[1:-1]]
                    if all(re.match(r'^[-:\s]+$', c) for c in cells):
                        continue
                    tag = "th" if i == 0 else "td"
                    th_style = "padding:10px 14px;border:1px solid #e2e8f0;text-align:left;font-weight:700;color:#1e293b;background:#f1f5f9;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;"
                    td_style = "padding:8px 14px;border:1px solid #e2e8f0;text-align:left;font-weight:400;color:#334155;"
                    style = th_style if tag == "th" else td_style
                    row_html = f"<{tag} style='{style}'>" + f"</{tag}><{tag} style='{style}'>".join(cells) + f"</{tag}>"
                    table_html += f"<tr>{row_html}</tr>"
                table_html += "</table>"
                html_parts.append(table_html)
            else:
                # Check if this paragraph is already a block-level HTML (like div or img)
                if p.strip().startswith("<div") or p.strip().startswith("<img"):
                    html_parts.append(p.strip())
                else:
                    content = p.replace("\n", "<br>")
                    html_parts.append(f"<p style='margin-top: 0; margin-bottom: 8px; line-height: 1.4; font-family: Arial, sans-serif;'>{content}</p>")
    
    return "".join(html_parts)

class DraftRequest(BaseModel):
    lead_id: int
    template_type: Optional[str] = "standard"



class ApproveRequest(BaseModel):
    approved_by: Optional[str] = "admin"
    cc: Optional[str] = None

class RejectRequest(BaseModel):
    rejected_reason: Optional[str] = ""

class BulkDraftRequest(BaseModel):
    lead_ids: List[int]
    cc: Optional[str] = None

class BulkSendRequest(BaseModel):
    lead_ids: List[int]
    cc: Optional[str] = None

class BulkActionRequest(BaseModel):
    lead_ids: List[int]
    action: str  # APPROVED, ARCHIVED, SENT, REJECTED
    reason: Optional[str] = None

class ScheduleRequest(BaseModel):
    scheduled_at: str

class BulkScheduleRequest(BaseModel):
    lead_ids: List[int]
    scheduled_at: str

@router.post("/emails/bulk-action")
def bulk_email_action(req: BulkActionRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        where_params = tuple(req.lead_ids)
        
        # User restriction
        user_clause = ""
        if user_id and user_id.lower() != "admin":
            user_clause = " AND user_id = %s"
            where_params += (user_id,)
        elif user_id and user_id.lower() == "admin":
            pass
        else:
            user_clause = " AND user_id IS NULL"

        # Update status
        cur.execute(f"UPDATE leads_raw SET email_status = %s, updated_at = NOW() WHERE id IN ({format_strings}) {user_clause}", (req.action, *where_params))
        
        # Log activity
        from app.models.lead import add_activity_log
        for lid in req.lead_ids:
            add_activity_log(lid, f"BULK_{req.action}", f"Bulk {req.action.lower()} action applied. {f'Reason: {req.reason}' if req.reason else ''}", "admin")

        conn.commit()
        cur.close()
        conn.close()

        invalidate_pending_drafts_cache(user_id)
        
        return {"message": f"Successfully updated {len(req.lead_ids)} leads to {req.action}"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

def normalize_lead(lead):
    if not lead:
        return {}
    if isinstance(lead, dict):
        return lead
    # Handle psycopg2 DictRow or actual tuples
    try:
        return dict(lead)
    except (TypeError, ValueError):
        if isinstance(lead, tuple) and len(lead) >= 4:
            return {
                "first_name": lead[1],
                "last_name": lead[2],
                "company_name": lead[3]
            }
    return {}

# Honorific/title prefixes that should never be used alone as a greeting name
_HONORIFICS = {"dr", "mr", "mrs", "ms", "miss", "prof", "sir", "madam", "rev", "capt", "col", "gen", "lt", "maj", "cmdr", "adm", "sgt", "cpl", "pvt", "hm", "er", "ca", "cs", "adv", "md", "phd"}

def clean_first_name(lead: dict) -> str:
    """
    Returns a greeting-safe FIRST name only for the lead.
    - Strips leading honorifics like 'Dr.', 'Mr.', 'Prof.' from first_name.
    - Falls back to last_name if first_name is ONLY an honorific (e.g. stored as 'Dr.').
    - Returns only the FIRST WORD so full names stored in first_name (e.g. 'Raajiv singhal')
      become just 'Raajiv'.
    - Falls back to 'there' if no usable name is found.
    """
    raw_first = (lead.get("first_name") or lead.get("name") or "").strip()
    raw_last  = (lead.get("last_name") or "").strip()

    # Strip trailing dot from honorific prefix check
    normalized = raw_first.rstrip(".").lower()

    if normalized in _HONORIFICS:
        # first_name is just a title — use first word of last_name if available
        if raw_last:
            return raw_last.strip().split()[0].capitalize()
        return "there"

    # Strip a leading honorific word (e.g. "Dr. Ashish Kumar" → ["Ashish", "Kumar"])
    parts = raw_first.split()
    if len(parts) > 1 and parts[0].rstrip(".").lower() in _HONORIFICS:
        parts = parts[1:]

    # Always return only the FIRST word (capitalize it)
    return parts[0].capitalize() if parts else (raw_last.split()[0].capitalize() if raw_last else "there")


def get_sender_profile(user_id: Optional[str]) -> dict:
    """Fetches the full sender profile for signature construction, using ID or falling back to defaults."""
    uid = normalize_user_id(user_id)
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Select all relevant signature fields
        cur.execute("SELECT full_name, username, job_title, phone, linkedin_url FROM users WHERE id = %s", (uid,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return dict(user)
    except Exception as e:
        logger.error(f"Error fetching sender profile: {e}")
    
    return {
        "full_name": "System Admin", 
        "username": "admin",
        "job_title": "ITTEAM", 
        "phone": "8527083798", 
        "linkedin_url": "https://linkedin.com"
    }

def heal_draft_content(email_draft: str, user_id: Optional[str], profile: Optional[dict] = None) -> str:
    if not email_draft:
        return email_draft
    
    # Resolve logged-in user details
    if profile is None:
        profile = get_sender_profile(user_id)
    sender_full_name = profile.get('full_name') or profile.get('username') or "Kajal Huria"
    sender_first_name = sender_full_name.split()[0] if sender_full_name else "Kajal"
    if sender_first_name.lower() in ["system", "admin", "team", "the", "test"]:
        if sender_first_name.lower() == "test":
            sender_first_name = "Test"
        else:
            sender_first_name = "Sravanthi"
    else:
        # Capitalize name nicely
        sender_first_name = sender_first_name.capitalize()
        
    healed = email_draft
    
    # 0. Resolve [[BACKEND_URL]] placeholder so images work during send flow
    backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    healed = healed.replace("[[BACKEND_URL]]", backend_url)
    
    # 0a. Protect image filenames from name replacement below
    healed = healed.replace("kajal.png", "[[KAJAL_IMG_PNG]]").replace("Kajal.png", "[[KAJAL_IMG_PNG]]")
    
    # 1. Case-insensitively replace any occurrence of "Kajal" with the logged-in user's first name
    if "kajal" in healed.lower():
        healed = re.sub(r"\bKajal\b", sender_first_name, healed, flags=re.IGNORECASE)
    
    # 0b. Restore protected image filenames
    healed = healed.replace("[[KAJAL_IMG_PNG]]", "kajal.png")
        
    # 2. Heal the subject line if this is the AI tech platform draft but has the generic subject
    healed_lower = healed.lower()
    is_ai_tech = (
        "hiring" in healed_lower or 
        "recruitment" in healed_lower or 
        "verification" in healed_lower or 
        "bgv" in healed_lower or 
        "hr tech" in healed_lower or
        "ats" in healed_lower or
        "100k+" in healed_lower
    )
    
    if is_ai_tech:
        if "strategic partnership" in healed_lower or "strategic investment" in healed_lower or "qvscl x" in healed_lower or "qvscl ×" in healed_lower:
            lines = healed.split("\n")
            if lines and lines[0].lower().startswith("subject:"):
                lines[0] = "Subject: AI-Powered Hiring Infrastructure Platform Company | 100K+ Recruiters | 250+ Companies |"
                healed = "\n".join(lines)
                
    # 3. Hospital-specific healing: detect by unique content fingerprints and upgrade signature
    hospital_fingerprints = [
        "uttar pradesh",
        "arpob",
        "ayush"
    ]
    # Check if this is likely the hospital draft (Ayush Sir's)
    is_hospital = any(fp in healed_lower for fp in hospital_fingerprints)
    
    if is_hospital:
        backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
        # We use a markdown image that the renderer will convert to a full-width banner
        banner_md = f"![Investment Opportunity Banner]({backend_url}/assets/PHOTO-2026-05-25-10-33-35.jpg)"
        hospital_disclaimer = """<strong>Strictly Private and Confidential.</strong><br><br>The information contained in this email is confidential, may be legally privileged, may constitute inside information and is intended solely and exclusively for the use of the intended addressee and any others who have been specifically authorized to receive it. Quantum Value Strategic Consulting does not provide legal, accounting or tax advice. Any statement in this email (including any attachments) regarding legal, accounting or tax matters was written in connection with the explanation of the matters described herein and was not intended or written to be relied upon by any person. Unauthorized dissemination, distribution, disclosure or other use of the contents of this email is strictly prohibited and may be unlawful. If you have received this email in error, please notify us immediately by return email and destroy this message and all copies thereof, including any attachments."""
        
        # NUCLEAR REGEX: If it's a hospital draft, catch anything starting with "Important:" and replace it.
        # This prevents any residual "Thank you" or old text from being left behind.
        old_disclaimer_regex = r"Important:.*$"
        
        # First, try to replace the old disclaimer nuclear-style (multiline)
        if re.search(r"Important:", healed, flags=re.IGNORECASE):
            healed = re.sub(r"Important:.*$", hospital_disclaimer, healed, flags=re.DOTALL | re.IGNORECASE)
        
        # Second, ensure the banner is present
        if "PHOTO-2026-05-25-10-33-35" not in healed:
            if "<strong>Strictly Private" in healed:
                 healed = healed.replace(
                    "<strong>Strictly Private",
                    f"{banner_md}\n\n<strong>Strictly Private"
                )
            else:
                # Appending banner and then disclaimer if somehow standard detection failed
                healed = healed.rstrip() + f"\n\n{banner_md}\n\n{hospital_disclaimer}"
                
    return healed

def inject_signature(body: str, profile: dict, lead_id: int) -> str:
    """Appends a premium standardized signature and mandatory unsubscribe link."""
    body_text = body.strip()
    body_lower = body_text.lower()
    
    # If unsubscribe already exists in body, strip it to avoid duplication,
    # then let the normal flow add the proper signature + unsubscribe link
    if "unsubscribe" in body_lower:
        lines = body_text.split("\n")
        lines = [l for l in lines if "unsubscribe" not in l.lower()]
        body_text = "\n".join(lines).strip()
        body_lower = body_text.lower()
    
    # 1. Strip existing signature to allow replacement by the current logged-in user
    # Look for the formal separator "--"
    if "--" in body_text:
        # Check if what follows -- looks like a signature (regards, sincerely, etc.)
        parts = body_text.rsplit("--", 1)
        after_sep = parts[1].lower()
        if any(x in after_sep for x in ["regards", "sincerely", "thanks", "analyst"]):
            body_text = parts[0].strip()
            body_lower = body_text.lower()

    # 2. Strip any trailing sign-offs to prevent duplication
    sign_offs = ["thanks & regards", "sincerely", "best regards", "thanks,", "regards,", "thanks and regards"]
    for s in sign_offs:
        if body_lower.endswith(s):
            body_text = body_text[:-(len(s))].strip()
            body_lower = body_text.lower()
            break

    name = profile.get('full_name') or profile.get('username') or 'The Team'
    name = " ".join([p.capitalize() for p in name.split()])
    title = profile.get('job_title') or 'Analyst'
    linkedin = profile.get('linkedin_url') or "https://www.linkedin.com/company/qvscl/"
    phone = profile.get('phone') or "8527083798"
    
    disclaimer = """Important: This message and its attachments are intended only for the addressee and may contain legally privileged and/or confidential information. If you are not the intended recipient, you are hereby notified that you must not use, disseminate, or copy this material in any form, or take any action based upon it. If you have received this message by error, please immediately delete it and its attachments and notify the sender at QV Strategic Consulting LLP by electronic mail message reply. Thank you."""

    # Active unsubscribe link
    unsub_link = f"https://qvscl.com/unsubscribe?lead_id={lead_id}"
    
    # Standardized signature in grey (fully left-aligned with no leading spaces)
    sig_html = f"""
<div style="color: #666666; font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; text-align: left; margin-top: 4px;">
<a href="{unsub_link}" style="color: #666666; text-decoration: underline;">Click here to unsubscribe</a><br>
--<br>
<i>Thanks &amp; Regards,</i><br>
<i><strong>{name}</strong></i><br>
<i>{title}</i><br>
<i><a href="https://qvscl.com" style="color: #0077b5; text-decoration: none;">Website</a> | <a href="{linkedin}" style="color: #0077b5; text-decoration: none;">LinkedIn</a></i><br>
<i>{phone}</i><br>
<div style="font-size: 10px; color: #999999; line-height: 1.2; margin-top: 6px;">
{disclaimer}
</div>
</div>
"""
    return body_text + sig_html

@router.post("/generate-draft")
@router.post("/generate-email")
def generate_draft_endpoint(req: DraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    return generate_email_internal(req, user_id)

def generate_email_internal(req: DraftRequest, user_id: Optional[str] = None):
    conn = None
    try:
        uid = normalize_user_id(user_id)
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if user_id and user_id.lower() != "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (req.lead_id, user_id))
        elif user_id and user_id.lower() == "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s", (req.lead_id,))
        else:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id IS NULL", (req.lead_id,))
            
        lead = cur.fetchone()

        if not lead:
            cur.close()
            return {"error": "Lead not found"}
        lead = normalize_lead(lead)
        
        profile = get_sender_profile(user_id)
        generator = EmailGenerator()
        
        # Select template
        if req.template_type == 'palak':
            cur.execute("SELECT content FROM prompts WHERE name = 'palak_mam_Draft_1' AND is_active = TRUE")
            palak_row = cur.fetchone()

            f_name = clean_first_name(lead)
            l_name = (lead.get("last_name") or "").strip()
            full_name = f"{f_name} {l_name}".strip()
            company = (lead.get("company_name") or lead.get("family_office_name") or "your organization").strip()
            sender_full_name = profile.get('full_name') or profile.get('username') or "the team"
            sender_title = profile.get('job_title') or ""
            sender_phone = profile.get('phone') or ""
            sender_linkedin = profile.get('linkedin_url') or "https://www.linkedin.com/company/qvscl/"

            if palak_row:
                template_body = palak_row["content"]
                body = template_body.replace("{{First Name}}", f_name).replace("{{first name}}", f_name).replace("{{first_name}}", f_name)
                body = body.replace("{{Full Name}}", full_name).replace("{{full_name}}", full_name)
                body = body.replace("{{Company Name}}", company).replace("{{Company}}", company).replace("{{company_name}}", company)
                body = body.replace("***{{Sender Name}}***", sender_full_name).replace("{{Sender Title}}", sender_title).replace("{{Sender Phone}}", sender_phone).replace("{{Sender LinkedIn}}", sender_linkedin).replace("{{Sender Linkedin}}", sender_linkedin)
                subject = f"Strategic Investment/Partnership Opportunity | QVSCL × {company}"
            else:
                email_data = generator.generate_palak_email(
                    lead,
                    sender_name=sender_full_name,
                    sender_linkedin=sender_linkedin
                )
                subject = email_data.get("subject", "Following up")
                body = email_data.get("body", "")
        elif req.template_type != 'standard':
            cur.execute("SELECT content FROM prompts WHERE name = %s AND prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE", (req.template_type,))
            row_t = cur.fetchone()
            
            if row_t:
                template_body = row_t["content"]
                f_name = clean_first_name(lead)

                l_name = (lead.get("last_name") or "").strip()
                full_name = f"{f_name} {l_name}".strip()
                company = (lead.get("company_name") or lead.get("family_office_name") or "your organization").strip()
                designation = (lead.get("designation") or "").strip()

                sender_full_name = profile.get('full_name') or profile.get('username') or "the team"
                sender_first_name = sender_full_name.split()[0] if sender_full_name else "Team"
                sender_title = (profile.get('job_title') or "").strip() or "Analyst"
                sender_phone = (profile.get('phone') or "").strip() or "8527083798"
                sender_linkedin = (profile.get('linkedin_url') or "").strip() or "https://www.linkedin.com/company/qvscl/"

                body = template_body
                replacements = [
                    ("{{First Name}}", f_name),
                    ("{{first name}}", f_name),
                    ("{{first_name}}", f_name),
                    ("{{Full Name}}", full_name),
                    ("{{full_name}}", full_name),
                    ("{{Company Name}}", company),
                    ("{{company_name}}", company),
                    ("{{Company}}", company),
                    ("{{Designation}}", designation),
                    ("***{{Sender Name}}***", sender_full_name),
                    ("{{Sender Full Name}}", sender_full_name),
                    ("{{Sender First Name}}", sender_first_name),
                    ("{{Sender Title}}", sender_title),
                    ("{{Sender Phone}}", sender_phone),
                    ("{{Sender LinkedIn}}", sender_linkedin),
                    ("{{Sender Linkedin}}", sender_linkedin),
                    ("[[BACKEND_URL]]", os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")),
                ]
                
                for placeholder, value in replacements:
                    reg = re.compile(re.escape(placeholder), re.IGNORECASE)
                    body = reg.sub(str(value or ""), body)

                subject = f"Strategic Partnership Opportunity | QVSCL × {company}"
            else:
                email_data = generator.generate_email(
                    lead, 
                    sender_name=profile.get('full_name') or profile.get('username'),
                    sender_linkedin=profile.get('linkedin_url') or "https://www.linkedin.com/company/qvscl/"
                )
                subject = email_data.get("subject")
                body = email_data.get("body")
        else:
            email_data = generator.generate_email(
                lead, 
                sender_name=profile.get('full_name') or profile.get('username'),
                sender_linkedin=profile.get('linkedin_url') or "https://www.linkedin.com/company/qvscl/"
            )
            subject = email_data.get("subject")
            body = email_data.get("body")
        
        if "SIG_START" in body or "SIG_END" in body:
            body_with_sig = body
        else:
            body_lower = body.lower()
            if "thanks & regards" in body_lower or "best regards" in body_lower:
                body_with_sig = body
            else:
                body_with_sig = inject_signature(body, profile, req.lead_id)

        body_lines = body_with_sig.split("\n")
        subject_found = False
        new_body_lines = []
        
        for line in body_lines:
            if not subject_found and "subject:" in line.lower():
                if ":" in line:
                    subject = line.split(":", 1)[1].strip()
                else:
                    subject = line.replace("Subject", "", 1).replace("subject", "", 1).strip()
                subject_found = True
            else:
                new_body_lines.append(line)
        
        if subject_found:
            body_with_sig = "\n".join(new_body_lines).strip()
        
        html_body = markdown_to_html(body_with_sig)
        email_content = f"Subject: {subject}\n\n{body_with_sig}"
        
        old_gmail_id = lead.get('gmail_draft_id')
        uid_int = int(normalize_user_id(user_id))
        if old_gmail_id:
            try:
                from app.services.google_service import get_gmail_service
                service = get_gmail_service(uid_int)
                if service:
                    service.users().drafts().delete(userId='me', id=old_gmail_id).execute()
                    logger.info(f"Deleted old Gmail draft {old_gmail_id}")
            except:
                pass

        gmail_draft_id = None
        draft_to_email = lead.get('email', '')
        if not draft_to_email:
            logger.warning(f"Skipping Gmail draft — lead {req.lead_id} has no email")
        try:
            from app.services.google_service import get_gmail_service
            import base64
            from email.mime.text import MIMEText
            service = get_gmail_service(uid_int)
            if service and draft_to_email:
                message = MIMEText(html_body, 'html')
                message['to'] = draft_to_email
                message['subject'] = subject
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                
                draft_body = {'message': {'raw': raw_message}}
                created_draft = service.users().drafts().create(userId='me', body=draft_body).execute()
                gmail_draft_id = created_draft.get('id')
                logger.info(f"Created NEW Gmail draft {gmail_draft_id} for Lead {req.lead_id}")
        except Exception as ge:
            logger.warning(f"Gmail draft sync failed: {ge}")
            gmail_draft_id = None

        cur.execute("""
            UPDATE leads_raw 
            SET email_draft = %s, email_status = 'PENDING_APPROVAL', updated_at = NOW(), gmail_draft_id = %s
            WHERE id = %s
        """, (email_content, gmail_draft_id, req.lead_id))
        conn.commit()

        invalidate_pending_drafts_cache(str(uid) if uid else None)

        try:
            from app.models.lead import add_activity_log
            add_activity_log(req.lead_id, "DRAFT_GENERATED", f"Email draft regenerated using '{req.template_type}'", profile.get('username') or "system")
        except:
            pass

        return {
            "message": "Draft generated",
            "draft_id": req.lead_id,
            "subject": subject,
            "body": body_with_sig,
            "gmail_draft_id": gmail_draft_id,
            "gmail_synced": gmail_draft_id is not None
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
# --- List Custom Draft Templates (for template picker modal) ---
@router.get("/custom-draft-templates")
def list_custom_draft_templates(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns CUSTOM_DRAFT type prompts filtered by the current user's ownership."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Seed owner_username for existing templates based on name pattern
        owner_seed = {
            "palak_mam_Draft_1": "palak",
            "palak_mam_corporate_advisory": "palak",
            "palak_mam_mna_fundraising": "palak",
            "yashika_draft_agritech": "yashika",
            "yashika_draft_ai_tech": "yashika",
            "ayush_sir_hospital_draft": "ayush",
            "kajal_mam_hyphen": "kajal",
            "kajal_mam_jv": "kajal",
            "kajal_mam_health_ecosystem": "kajal",
            "kajal_mam_agritech": "kajal",
            "kajal_mam_qvscl_intro": "kajal",
        }
        for tpl_name, owner in owner_seed.items():
            cur.execute("UPDATE prompts SET owner_username = %s WHERE name = %s AND (owner_username IS NULL OR owner_username != %s)", (owner, tpl_name, owner))
        conn.commit()

        # Seed kajal_mam_agritech if it doesn't exist (will get correct content from the update below)
        cur.execute("SELECT id FROM prompts WHERE name = 'kajal_mam_agritech'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO prompts (name, description, content, prompt_type) VALUES (%s, %s, %s, 'CUSTOM_DRAFT')",
                ("kajal_mam_agritech", "Climate Agritech Platform fundraising draft (USD 500K-1M)", "placeholder")
            )
            conn.commit()

        # Self-healing database update:
        # Check if 'yashika_draft_ai_tech' has the correct placeholder and Subject prefix.
        # If not, update it dynamically in the database so the user doesn't need to run scripts!
        latest_description = "AI-Powered Hiring Infrastructure Platform fundraising draft ($1M)"
        latest_content = """Subject: AI-Powered Hiring Infrastructure Platform Company | 100K+ Recruiters | 250+ Companies |

Dear {{First Name}},

I hope you're doing well.

I'm {{Sender First Name}} from QVSCL (Gurugram), a strategic advisory firm working with high-growth early-stage ventures. We are currently raising a round for a platform building a <strong>vertical AI-powered hiring intelligence layer</strong>, combining AI agents, recruitment workflows, and trust-based verification infrastructure.

<strong>Business Overview</strong>

<strong>Headquarters:</strong> Singapore (with India as a 100% owned subsidiary and a US joint venture)

<strong>Founded:</strong> By industry leaders with 20+ years of experience across HR, fintech, and enterprise technology

<strong>Focus:</strong> Building a unified hiring infrastructure platform that automates and optimizes end-to-end recruitment workflows - spanning sourcing, screening, evaluation, and background verification

<strong>Platform Offering:</strong> A full-stack hiring infrastructure platform integrating applicant tracking, multi-channel sourcing, AI-driven screening, and native background verification into a single system

<strong>Technology:</strong> AI-powered vertical agents enabling sourcing, scheduling, interviewing, and verification workflows, supported by a proprietary trust graph that improves candidate matching and reduces fraud over time

<strong>Revenue Model:</strong> Enterprise SaaS with multi-layered monetization across hiring workflows, verification services, and AI-driven automation modules, enabling scalable and recurring revenue streams

<strong>Core Differentiation:</strong> Unlike fragmented HR tech stacks, the platform functions as a <strong>system of intelligence for hiring</strong> - combining workflows, data, and verification into a unified infrastructure layer that improves decision-making over time. Positioned alongside global AI hiring platforms, with differentiated focus on integrated trust infrastructure and verification layers.

<em>Designed to become the underlying infrastructure layer for hiring in an era of AI-generated talent and rising trust deficits</em>

<strong>Industry Overview</strong>

Hiring at scale remains highly inefficient despite large market size:

• 3.6M job vacancies are posted monthly in India, but only 2.1M hires are completed
• 1.5M workforce gap leading to significant unrealized economic output
• 80% of employers face talent shortages
• Hiring processes remain largely manual and fragmented

<strong>Market Opportunity:</strong>

• Global Hiring & Recruitment Tech TAM: $150B+
• Rapid shift toward AI-driven automation, trust, and verification layers (35-45% CAGR)

<strong>Problems</strong>

<strong>HR & Recruiter Challenges</strong>

• 180 applications per hire leading to massive screening overload
• Recruiters managing significantly higher workloads without increased team size
• 57% of time spent on repetitive "data janitorial" tasks

<strong>Process Inefficiencies</strong>

• Fragmented workflows across 20+ tools (ATS, sourcing, BGV, onboarding)
• Manual data handling and poor system integrations
• Long hiring cycles (average 44 days to fill roles)

<strong>Trust & Quality Issues</strong>

• 70% resumes contain inaccuracies
• AI-generated and unverified profiles flooding pipelines
• High attrition and hiring inefficiencies due to poor matching

<strong>Solutions</strong>

• <strong>AI Hiring Co-Pilot:</strong> Automates sourcing, screening, and evaluation
• <strong>Unified Infrastructure:</strong> One system across ATS, sourcing, and verification
• <strong>Trust Layer:</strong> Proprietary graph improving match quality and fraud detection
• <strong>Background Verification:</strong> Native BGV system with 20+ checks across identity, employment, education, and criminal records
• <strong>Workflow Automation:</strong> Eliminates manual processes, reducing HR workload and improving hiring efficiency
• <strong>Scalable Architecture:</strong> APIs and integrations with HRMS/ATS systems enabling enterprise-grade deployment

<strong>Validations & Traction</strong>

• 100K+ companies onboarded on the platform
• 250+ enterprise customers across 50+ industries
• Currently in advanced discussions for potential onboarding across multiple enterprise accounts
• Rapid enterprise adoption across India and international markets, with strong demand from US-based customers
• 60% of current and projected revenue driven by US market demand
• 94% customer retention rate

<strong>Operational Impact:</strong>

• Near real-time hiring cycles (2-3 days vs 44 days industry average)
• Background verification TAT reduced from 15 days to 2 days
• 40%+ reduction in HR operational workload

<strong>Fundraise</strong>

• Total capital raised in previous rounds: $3M
• Currently raising: $1M - $3M

Happy to walk you through a quick live product demo showcasing the platform in action

If this aligns with your portfolio focus and does not conflict with it, I'd be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.

For more details about our services:

[Website](https://qvscl.com) | [Linkedin](https://www.linkedin.com/company/qvscl/)

Looking forward to your response.

SIG_START
--
Thanks & Regards,
***{{Sender Name}}***
{{Sender Title}}
[Website](https://www.qvscl.com) | [LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}
<strong>Strictly Private and Confidential.</strong>

The information contained in this email is confidential, may be legally privileged, may constitute inside information and is intended solely and exclusively for the use of the intended addressee and any others who have been specifically authorized to receive it. Quantum Value Strategic Consulting does not provide legal, accounting or tax advice. Any statement in this email (including any attachments) regarding legal, accounting or tax matters was written in connection with the explanation of the matters described herein and was not intended or written to be relied upon by any person. Unauthorized dissemination, distribution, disclosure or other use of the contents of this email is strictly prohibited and may be unlawful. If you have received this email in error, please notify us immediately by return email and destroy this message and all copies thereof, including any attachments.
SIG_END"""
        
        # Select and verify if the database entry needs to be fixed.
        cur.execute("SELECT content FROM prompts WHERE name = 'yashika_draft_ai_tech'")
        row = cur.fetchone()
        if not row or "Subject:" not in row[0] or "Kajal" in row[0] or "Total capital raised in previous rounds: $3M" not in row[0]:
            # Perform automatic update to correct placeholder, layout and subject prefix
            cur.execute(
                "UPDATE prompts SET content = %s, description = %s WHERE name = 'yashika_draft_ai_tech'",
                (latest_content, latest_description)
            )
            conn.commit()

        # Ayush Sir Hospital Template Self-Healing
        hospital_description = "Integrated Multi-Site Hospital Platform in Eastern Uttar Pradesh ($240 Cr EV)"
        hospital_content = """Subject: Strategic Investment Opportunity – Integrated Multi-Site Hospital Platform in Eastern Uttar Pradesh

Dear {{First Name}},

Greetings for the day.

I hope this message finds you well.

My name is {{Sender First Name}}, an Investment Banker based out of Gurugram, representing QV Strategic Consulting LLP, an Investment Banking firm focused on strategic transactions and growth capital advisory across high-potential sectors in India.

We are currently advising on a <strong>strategic investment / acquisition opportunity</strong> for a rapidly growing <strong>hospitals operating across Eastern Uttar Pradesh, one of India's largest yet significantly underserved healthcare markets</strong>.

This opportunity combines:

• <strong>Strong existing profitability</strong>
• <strong>Embedded operating leverage</strong>
• <strong>Asset-backed downside protection</strong>
• <strong>Infrastructure-ready scalability</strong>
• <strong>Attractive cash-flow characteristics</strong>
• <strong>Significant regional healthcare demand tailwinds</strong>
• <strong>Healthy EBITDA Margins</strong>
• <strong>PAT Positive Operations</strong>

At a time when institutional investors and strategic healthcare operators are actively seeking scalable regional healthcare platforms, this business offers a differentiated opportunity to acquire a profitable and operationally established healthcare ecosystem ahead of its next phase of expansion.

<strong>Investment Snapshot</strong>

| Particulars | Current Metrics |
| --- | --- |
| Net Revenue | ~₹49.2 Cr |
| EBITDA | ~₹16.8 Cr |
| EBITDA Margin | ~34.2% |
| PAT | ~₹8.4 Cr |
| Installed Capacity | 225 Beds |
| ARPOB / RPOB | ~₹26,000 |
| Average Length of Stay | 3.8 Days |
| Blended Occupancy | ~28.3% |

<strong>Why This Opportunity Stands Out:</strong>

<strong>1. Rare Combination of High Margins + Underutilized Capacity</strong>

The platform is already generating <strong>~34.2% EBITDA margins</strong> despite occupancy levels remaining <strong>significantly below mature hospital-chain benchmarks</strong>.

This is particularly important because current profitability is being generated <em>before</em> operational maturity.

The business currently operates at only <strong>~28.3% blended occupancy across 225 installed beds</strong>, creating substantial embedded operating leverage potential as utilization scales.

Unlike many healthcare businesses where profitability is already fully optimized, this platform offers investors the ability to participate in future EBITDA expansion through:

• Occupancy ramp-up
• Clinician additions
• Improved referral conversion
• Diagnostics attachment
• Better throughput utilization
• Commercial optimization

while leveraging an already operational infrastructure base.

<strong>2. Strong Monetization Metrics Already Achieved</strong>

Despite relatively low occupancy, the platform has already achieved <strong>ARPOB levels of approximately ₹26,000</strong>, indicating strong monetization quality and healthy case-mix realization for the region.

This is a key indicator because it demonstrates that the current opportunity is not dependent on aggressive pricing assumptions - monetization strength already exists at current throughput levels.

<strong>3. Attractive Revenue Quality & Cash Conversion</strong>

The business benefits from a highly favorable payer mix:

| Revenue Mix | Contribution |
| --- | --- |
| Cash | ~58.3% |
| Corporate | ~39.0% |
| TPA | Only ~2.7% |

This significantly <strong>reduces</strong>:

• Receivable cycles
• Insurance adjudication delays
• Working capital inefficiencies
• Collection stress

and supports stronger cash generation compared to hospital businesses with heavier TPA dependence.

In addition, revenue remains balanced between:

• <strong>IPD Revenue:</strong> ~50.7%
• <strong>OPD + Daycare Revenue:</strong> ~49.3%

creating diversified patient monetization and recurring engagement opportunities.

<strong>4. Diversified Clinical Platform</strong>

The platform has established a broad tertiary-care ecosystem across multiple specialties including:

• Cardiology
• Nephrology
• Neuro Sciences
• Orthopedics
• Gynecology
• Pediatrics
• Physician Medicine

Importantly, the business is not dependent on a single specialty vertical, improving resilience and earnings visibility.

The <strong>top 8 specialties contribute ~85.5% of specialty revenue</strong>, providing a balanced mix of bread-and-butter healthcare demand along with higher-acuity procedures.

<strong>5. Infrastructure-Ready Growth Platform</strong>

A significant portion of the infrastructure and operating ecosystem is already in place.

Management indicates that only <strong>~₹5 Cr</strong> of selective readiness and productivity capex may be required to support:

• Equipment refresh
• Throughput enhancement
• Facility activation
• Productivity improvement
• Selective expansion initiatives

This materially lowers execution and capital deployment risk relative to greenfield hospital expansion strategies.

<strong>6. Strong Historical Momentum</strong>

| Metric | Growth |
| --- | --- |
| Core Hospital EBITDA Growth | ~9.9% |
| Occupancy Growth | ~14.3% |
| ARPOB Growth | ~4.0% |

The simultaneous improvement in occupancy and monetization highlights strengthening operational quality.

<strong>7. Asset-Backed Downside Protection</strong>

The transaction includes a flagship owned hospital campus providing meaningful underlying hard-asset value within the overall transaction structure.

This creates an additional layer of downside support while preserving upside from future operating scale and institutionalization.

<strong>8. Attractive Industry Positioning & Regional Tailwinds</strong>

Eastern Uttar Pradesh remains significantly underserved in organized tertiary and super-specialty healthcare penetration relative to metropolitan India.

Simultaneously, broader Indian healthcare sector dynamics remain highly favorable:

• Increasing formalization of healthcare delivery
• Rising patient preference for organized providers
• Strong Tier-2 and Tier-3 healthcare demand growth
• Limited availability of scalable regional healthcare assets
• Expanding institutional capital participation in healthcare

These factors continue to support premium valuations for high-quality regional healthcare platforms with scalable infrastructure and operating visibility.

<strong>9. Indicative Transaction Overview</strong>

The proposed transaction perimeter includes:

• Operating hospital business
• Owned primary hospital campus
• Secondary leased campus operations

Currently, the transaction is being discussed at an indicative enterprise valuation of approximately <strong>₹240 Cr</strong> depending on structure and diligence outcomes.

We believe this opportunity represents a compelling combination of:

• <strong>~34.2% existing EBITDA margins</strong>
• <strong>Strong current cash-flow profile</strong>
• <strong>Strong existing profitability</strong>
• <strong>Embedded operating leverage from underutilized capacity</strong>
• <strong>Infrastructure-ready scalability</strong>
• <strong>Regional healthcare demand expansion</strong>
• <strong>Strong monetization characteristics</strong>
• <strong>Asset-backed downside support</strong>

At QV Strategic Consulting LLP, we specialize in facilitating <strong>high-potential investment opportunities for long-term capital partners</strong>. I would be happy to schedule a 30-minute virtual call to discuss this opportunity further.

I have attached the <strong>QV Strategic Consulting business profile</strong> and <strong>Investment Teaser</strong> for your reference.

SIG_START
--
Thanks & Regards,

<strong>***{{Sender Name}}***</strong>
{{Sender Title}}
[Website](https://www.qvscl.com) | [LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}

![Investment Opportunity Banner]([[BACKEND_URL]]/assets/PHOTO-2026-05-25-10-33-35.jpg)

<strong>Strictly Private and Confidential.</strong>

The information contained in this email is confidential, may be legally privileged, may constitute inside information and is intended solely and exclusively for the use of the intended addressee and any others who have been specifically authorized to receive it. Quantum Value Strategic Consulting does not provide legal, accounting or tax advice. Any statement in this email (including any attachments) regarding legal, accounting or tax matters was written in connection with the explanation of the matters described herein and was not intended or written to be relied upon by any person. Unauthorized dissemination, distribution, disclosure or other use of the contents of this email is strictly prohibited and may be unlawful. If you have received this email in error, please notify us immediately by return email and destroy this message and all copies thereof, including any attachments.
SIG_END"""

        # FORCE UPDATE EVERY TIME the templates are listed
        cur.execute(
            "UPDATE prompts SET content = %s, description = %s WHERE name = 'ayush_sir_hospital_draft'",
            (hospital_content, hospital_description)
        )

        # Palak Mam Corporate Advisory — force update
        palak_corp_description = "Corporate Advisory / Equity Fund Raising Services — QVSCL Introduction"
        palak_corp_content = """Subject: Corporate Advisory/ Equity Fund Raising Services.

Dear {{First Name}},

Greetings from QVSCL!

I hope you're doing well.

I'm excited to introduce QV Strategic Consulting, your trusted partner for driving sustainable capital growth. With extensive experience across diverse industries, we combine strategic expertise, innovation, and hands-on execution to help businesses achieve their goals.

<strong>Key Areas of Expertise:</strong>

• Preparation to IPO – Standardizing information systems, due diligence, information memorandum, and more.
• Fund Raising – Equity and debt financing solutions tailored to your needs.
• Board Advisory – Strategic guidance to enhance governance and decision-making.
• Implementing Partner – Strengthening management teams for seamless execution.
• Fostering Strategic Partnerships & Alliances – Facilitating joint ventures, mergers, and acquisitions.
• Strategic Business Planning – Crafting actionable roadmaps for long-term success.

To learn more about how we can support your growth ambitions, see our [website](https://qvscl.com) or connect with us on [LinkedIn](https://www.linkedin.com/company/qvscl/).

We'd love to schedule a virtual meeting at your convenience to explore potential collaboration. Kindly share your availability, and we'll coordinate a suitable time.

Attached, you'll find our company profile for your reference. Looking forward to connecting!

SIG_START
--
Thanks & Regards,

***{{Sender Name}}***
{{Sender Title}}
[Website](https://www.qvscl.com) | [LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}

<strong>Strictly Private and Confidential.</strong>

The information contained in this email is confidential, may be legally privileged, may constitute inside information and is intended solely and exclusively for the use of the intended addressee and any others who have been specifically authorized to receive it. Quantum Value Strategic Consulting does not provide legal, accounting or tax advice. Any statement in this email (including any attachments) regarding legal, accounting or tax matters was written in connection with the explanation of the matters described herein and was not intended or written to be relied upon by any person. Unauthorized dissemination, distribution, disclosure or other use of the contents of this email is strictly prohibited and may be unlawful. If you have received this email in error, please notify us immediately by return email and destroy this message and all copies thereof, including any attachments.
SIG_END"""

        cur.execute(
            "UPDATE prompts SET content = %s, description = %s WHERE name = 'palak_mam_corporate_advisory'",
            (palak_corp_content, palak_corp_description)
        )
        if cur.rowcount == 0:
            cur.execute(
                "INSERT INTO prompts (name, description, content, prompt_type) VALUES ('palak_mam_corporate_advisory', %s, %s, 'CUSTOM_DRAFT')",
                (palak_corp_description, palak_corp_content)
            )
        conn.commit()

        # 5. Yashika Agritech Template
        agritech_description = "Climate Agritech Platform fundraising draft (USD 500K-1M)"
        agritech_content = """Subject: Climate Agritech Platform | ₹5.1Cr Revenue | 105% YoY Growth | 1.24L+ Lives Impacted

Dear {{First Name}},

I hope you're doing well.

I'm {{Sender Name}} from QVSCL (Gurugram), a strategic advisory firm working with high-growth early-stage ventures. We are currently raising a round for a **climate-focused agritech platform** that is **building a full-stack renewable energy marketplace for rural India**.

**Business Overview**

* **Sector**: Agritech / Climate / Social Impact
* **Stage**: Revenue-generating, growth-stage
* **Positioning**: India's first curated marketplace for renewable & green energy products for farmers and rural households
* **Platform Offering**:
* Multi-brand marketplace with **60+ brands and 200+ SKUs** across solar, biogas, and green energy solutions
* End-to-end solutions spanning product discovery, advisory, deployment, and after-sales service
* AI-enabled touchpoints including chatbots and localized support
* **Business Model**:
* Phygital distribution model combining **AI-enabled digital platform + village-level offline stores**
* Asset-light approach with **franchise-led last-mile distribution**
* Multiple revenue streams across **B2C sales, B2B projects, partnerships, franchise fees, and AMC services**

**Problems**

Rural India faces structural inefficiencies in energy access and agri productivity:
* High dependence on **firewood, diesel, and unreliable electricity**
* Limited access to **modern technologies and advisory support**
* Fragmented distribution through traditional dealer networks limits penetration

**Solutions**

A **one-stop, full-stack renewable energy platform** addressing access, affordability, and adoption:
* **Phygital Marketplace**: Seamless online + offline distribution network
* **AI-led Advisory**: Personalized product recommendations and assisted buying
* **Last-Mile Reach**: Deep rural penetration via trained partners and franchise stores
* **Integrated Offering**: Solar, biogas, thermal, and green energy products under one platform
* **Value-Added Services**: Financing support, insurance, and long-term after-sales service

**Traction & Impact**

* **Revenue**: INR 5.1 Cr achieved till Feb'26 with ~105% YoY growth
* **Advance Orders**: INR 2 Cr pipeline
* **On-ground Impact (FY20-25)**:
* 1,24,153+ lives impacted; 1,10,000+ women impacted
* 2,070+ tons of CO₂ emissions abated
* 66,000+ green jobs created; 900+ acres irrigated via solar
* Large-scale deployment of renewable energy products across rural India

**Differentiation**

* **First-mover advantage** in building a **renewable energy marketplace with advisory layer**
* Strong **last-mile rural distribution network** vs. e-commerce-led competitors
* Integrated stack combining **commerce, financing, service, and impact delivery**

**Fundraise**

* **Raising**: USD 500K - 1M
* **Use of Funds**: Expansion, product development (AgriVoltaics), team scale-up, and market expansion

If this aligns with your portfolio focus and does not conflict with it, I'd be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.

For more details about our services: [Website](https://qvscl.com) | [Linkedin](https://www.linkedin.com/company/qvscl/)

Looking forward to your response.

SIG_START
--
**Thanks & Regards,**

***{{Sender Name}}***
{{Sender Title}}
[LinkedIn]({{Sender LinkedIn}})
{{Sender Phone}}
SIG_END"""

        cur.execute(
            "UPDATE prompts SET content = %s, description = %s WHERE name = 'yashika_draft_agritech'",
            (agritech_content, agritech_description)
        )
        if cur.rowcount == 0:
            cur.execute(
                "INSERT INTO prompts (name, description, content, prompt_type) VALUES ('yashika_draft_agritech', %s, %s, 'CUSTOM_DRAFT')",
                (agritech_description, agritech_content)
            )
        conn.commit()

        # Also update kajal_mam_agritech with same content
        cur.execute(
            "UPDATE prompts SET content = %s, description = %s, owner_username = 'kajal' WHERE name = 'kajal_mam_agritech'",
            (agritech_content, agritech_description)
        )
        conn.commit()
            
        # Filter by owner_username so each user only sees their own templates
        # ADMIN users see ALL templates
        owner_filter = None
        is_admin = False
        if user_id:
            try:
                cur.execute("SELECT username, full_name, role FROM users WHERE id = %s", (int(user_id),))
                user_row = cur.fetchone()
                if user_row:
                    role_val = user_row['role'] if isinstance(user_row, dict) else user_row[2]
                    if role_val and str(role_val).upper() == 'ADMIN':
                        is_admin = True
                    uname = str(user_row['username'] or '').lower()
                    fname = str(user_row['full_name'] or '').lower()
                    owner_filter = uname.split('.')[0] or fname.split()[0] if fname else uname
            except Exception:
                pass

        if is_admin:
            # Admin sees all custom templates
            cur.execute("SELECT id, name, description, content FROM prompts WHERE prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE ORDER BY id ASC")
        elif owner_filter:
            cur.execute("SELECT id, name, description, content FROM prompts WHERE prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE AND owner_username = %s ORDER BY id ASC", (owner_filter,))
        else:
            cur.execute("SELECT id, name, description, content FROM prompts WHERE prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE AND owner_username IS NULL ORDER BY id ASC")
        rows = cur.fetchall()
        logger.info(f"{len(rows)} templates found for user_id={user_id} (owner_filter={owner_filter}, is_admin={is_admin})")
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        return []

class TemplateDraftRequest(BaseModel):
    lead_id: int
    template_name: str  # e.g. "palak_mam_Draft_1"

@router.post("/generate-draft-from-template")
def generate_draft_from_template(req: TemplateDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Generate a draft using a fixed custom template, replacing {{First Name}}, {{Company Name}} etc."""
    return _generate_template_draft_inner(req.lead_id, req.template_name, user_id)


def _generate_template_draft_inner(lead_id: int, template_name: str, user_id: Optional[str]) -> dict:
    """Core logic for generating a template draft. Used by single and bulk endpoints."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Resolve User ID
        uid = normalize_user_id(user_id)

        # Fetch lead
        if user_id and user_id.lower() != "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (lead_id, uid))
        elif user_id and user_id.lower() == "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s", (lead_id,))
        else:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id IS NULL", (lead_id,))

        lead = cur.fetchone()
        if not lead:
            return {"error": "Lead not found"}
        lead = normalize_lead(lead)

        # Fetch template
        cur.execute("SELECT content FROM prompts WHERE name = %s AND prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE", (template_name,))
        tpl_row = cur.fetchone()
        cur.close()
        conn.close()

        if not tpl_row:
            return {"error": f"Template '{template_name}' not found"}

        template_body = tpl_row["content"]

        # Resolve lead fields
        first_name = clean_first_name(lead)  # strips Dr./Mr./Mrs. etc.
        last_name  = (lead.get("last_name") or "").strip()
        full_name  = f"{first_name} {last_name}".strip()
        company    = (lead.get("company_name") or lead.get("family_office_name") or "your organization").strip()
        designation= (lead.get("designation") or "").strip()

        # Subject
        subject = f"Strategic Partnership Opportunity | QVSCL × {company}"

        # Resolve sender fields for dynamic templates
        profile = get_sender_profile(user_id)
        sender_full_name = profile.get('full_name') or profile.get('username') or "the team"
        sender_first_name = sender_full_name.split()[0] if sender_full_name else "Team"
        sender_title = (profile.get('job_title') or "").strip() or "Analyst"
        sender_phone = (profile.get('phone') or "").strip() or "8527083798"
        sender_linkedin = (profile.get('linkedin_url') or "").strip() or "https://www.linkedin.com/company/qvscl/"

        # Replace all placeholders case-insensitively
        body = template_body
        replacements = [
            ("{{First Name}}", first_name),
            ("{{first name}}", first_name),
            ("{{first_name}}", first_name),
            ("{{Full Name}}", full_name),
            ("{{full_name}}", full_name),
            ("{{Company Name}}", company),
            ("{{company_name}}", company),
            ("{{Company}}", company),
            ("{{Designation}}", designation),
            # Sender placeholders
            ("***{{Sender Name}}***", sender_full_name),
            ("{{Sender Name}}", sender_full_name),
            ("{{Sender Full Name}}", sender_full_name),
            ("{{Sender First Name}}", sender_first_name),
            ("{{Sender Title}}", sender_title),
            ("{{Sender Phone}}", sender_phone),
            ("{{Sender LinkedIn}}", sender_linkedin),
            # Dynamic Backend URL for images/assets
            ("[[BACKEND_URL]]", os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")),
        ]

        for placeholder, value in replacements:
            # Use case-insensitive replacement for flexibility
            reg = re.compile(re.escape(placeholder), re.IGNORECASE)
            body = reg.sub(str(value or ""), body)

        # --- NEW: Extract Subject from template if it exists ---
        final_subject = subject  # Default
        final_body_lines = []
        subject_found = False

        body_lines = body.split("\n")
        for line in body_lines:
            if not subject_found and "subject:" in line.lower():
                # Extract the subject (skip "Subject: " part)
                if ":" in line:
                    final_subject = line.split(":", 1)[1].strip()
                else:
                    final_subject = line.replace("Subject", "", 1).replace("subject", "", 1).strip()
                subject_found = True
            else:
                final_body_lines.append(line)

        final_body = "\n".join(final_body_lines).strip()

        # Inject logged-in user's signature ONLY if the template doesn't already embed one
        profile = get_sender_profile(user_id)
        if "SIG_START" in final_body or "SIG_END" in final_body:
            # Template already has an embedded signature block — keep as-is
            body_with_sig = final_body
        else:
            # Prevent double signature if the template body ended with a sign-off but no marker
            body_lower = final_body.lower().strip()
            if "thanks & regards" in body_lower or "best regards" in body_lower or body_lower.endswith("--"):
                body_with_sig = final_body
            else:
                body_with_sig = inject_signature(final_body, profile, lead_id)

        # RE-GENERATE html_body AFTER deduplication
        html_body = markdown_to_html(body_with_sig)

        # Full content for local DB storage
        email_content = f"Subject: {final_subject}\n\n{body_with_sig}"

        # --- Delete OLD Gmail Draft if it exists ---
        old_gmail_id = lead.get('gmail_draft_id')
        uid_t = int(normalize_user_id(user_id))
        if old_gmail_id:
            try:
                from app.services.google_service import get_gmail_service
                service = get_gmail_service(uid_t)
                if service:
                    service.users().drafts().delete(userId='me', id=old_gmail_id).execute()
                    logger.info(f"🗑️ Deleted old Gmail draft {old_gmail_id} (template)")
            except:
                pass

        # --- Sync to Gmail Drafts (with PDF attachments) ---
        gmail_draft_id = None
        to_email = lead.get('email', '')
        if not to_email:
            logger.warning(f"⚠️ Skipping Gmail draft — lead {lead_id} has no email")
        try:
            from app.services.google_service import get_gmail_service
            import base64
            from email.mime.multipart import MIMEMultipart
            from email.mime.application import MIMEApplication
            from email.mime.text import MIMEText
            service = get_gmail_service(uid_t)
            if service and to_email:
                msg = MIMEMultipart('mixed')
                msg_body = MIMEMultipart('alternative')
                msg_body.attach(MIMEText(html_body, 'html'))
                msg.attach(msg_body)
                msg['to'] = to_email
                msg['subject'] = final_subject
                # Attach PDFs based on template name
                try:
                    tpl_attachments = TEMPLATE_ATTACHMENT_MAP.get(template_name, [])
                    if tpl_attachments:
                        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")
                        for att in tpl_attachments:
                            fpath = os.path.join(assets_dir, att["name"])
                            if os.path.exists(fpath):
                                with open(fpath, "rb") as f:
                                    part = MIMEApplication(f.read(), Name=att["name"])
                                    part['Content-Disposition'] = f'attachment; filename="{att["name"]}"'
                                    msg.attach(part)
                                logger.info(f"📎 Attached {att['name']} to Gmail draft")
                            else:
                                logger.warning(f"⚠️  Attachment not found: {fpath}")
                except Exception as ae:
                    logger.warning(f"⚠️  Attachment sync failed for draft: {ae}")
                raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
                draft_body = {'message': {'raw': raw_message}}
                created_draft = service.users().drafts().create(userId='me', body=draft_body).execute()
                gmail_draft_id = created_draft.get('id')
                logger.info(f"✅ Created NEW Gmail draft {gmail_draft_id} for Lead {lead_id} (template-html)")
        except Exception as ge:
            logger.warning(f"⚠️  Gmail draft sync failed: {ge}")
            gmail_draft_id = None

        # Save to DB (with gmail_draft_id and draft_template_used)
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        cur2.execute("""
            UPDATE leads_raw
            SET email_draft = %s, email_status = 'PENDING_APPROVAL', updated_at = NOW(), gmail_draft_id = %s, draft_template_used = %s
            WHERE id = %s
        """, (email_content, gmail_draft_id, template_name, lead_id))
        conn2.commit()
        cur2.close()
        conn2.close()

        invalidate_pending_drafts_cache(str(uid) if uid else None)

        try:
            from app.models.lead import add_activity_log
            add_activity_log(lead_id, "DRAFT_GENERATED", f"Custom template draft '{template_name}' generated {'(Gmail synced ✅)' if gmail_draft_id else ''}", "system")
        except:
            pass

        return {
            "message": "Draft generated from template",
            "draft_id": lead_id,
            "subject": final_subject,
            "body": body_with_sig,
            "template": template_name,
            "gmail_draft_id": gmail_draft_id,
            "gmail_synced": gmail_draft_id is not None
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


class BulkTemplateDraftRequest(BaseModel):
    lead_ids: list[int]
    template_name: str

import uuid as _uuid
import threading as _threading

_bulk_template_progress: dict = {}

@router.post("/bulk-generate-draft-from-template")
def bulk_generate_draft_from_template(req: BulkTemplateDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Generate drafts for multiple leads using a template, processed in parallel. Returns immediately with batch_id for progress polling."""
    if not req.lead_ids:
        return {"error": "No lead IDs provided", "batch_id": None}

    batch_id = str(_uuid.uuid4())
    _bulk_template_progress[batch_id] = {
        "total": len(req.lead_ids),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "status": "running"
    }

    def _run():
        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(_generate_template_draft_inner, lid, req.template_name, user_id): lid for lid in req.lead_ids}
                for future in as_completed(futures):
                    lid = futures[future]
                    try:
                        res = future.result()
                        p = _bulk_template_progress[batch_id]
                        p["processed"] += 1
                        if "error" not in res:
                            p["success"] += 1
                        else:
                            p["failed"] += 1
                    except Exception:
                        _bulk_template_progress[batch_id]["processed"] += 1
                        _bulk_template_progress[batch_id]["failed"] += 1
        except Exception as e:
            _bulk_template_progress[batch_id]["status"] = "error"
            _bulk_template_progress[batch_id]["error"] = str(e)
        else:
            _bulk_template_progress[batch_id]["status"] = "done"
        # Cleanup after 5 minutes
        _threading.Timer(300, lambda: _bulk_template_progress.pop(batch_id, None)).start()

    _threading.Thread(target=_run, daemon=True).start()
    return {"batch_id": batch_id, "total": len(req.lead_ids)}

@router.get("/bulk-progress/{batch_id}")
def get_bulk_progress(batch_id: str):
    """Poll this endpoint to get real-time progress of a bulk draft generation job."""
    prog = _bulk_template_progress.get(batch_id)
    if not prog:
        return {"status": "not_found"}
    return prog



# ---------------------------------------------------------------------------
# Template → PDF Attachment Mapping
# Each template specifies which PDFs get attached (shown in the draft preview
# and physically attached when the email is sent from email_service.py).
# ---------------------------------------------------------------------------
TEMPLATE_ATTACHMENT_MAP = {
    "ayush_sir_hospital_draft": [
        {"name": "QVSCL Company Profile.pdf",                                        "size": "1.7 MB",  "type": "application/pdf"},
        {"name": "eastern_up_hospital_investor_teaser_v5b_investorfriendly (2).pdf", "size": "202 KB", "type": "application/pdf"},
    ],
    "yashika_draft_ai_tech": [
        {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB",  "type": "application/pdf"},
        {"name": "Lalit_Huria_Profile.pdf",   "size": "250 KB",  "type": "application/pdf"},
    ],
    "yashika_draft_agritech": [
        {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB",  "type": "application/pdf"},
        {"name": "Lalit_Huria_Profile.pdf",   "size": "250 KB",  "type": "application/pdf"},
    ],
    "kajal_mam_agritech": [
        {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB",  "type": "application/pdf"},
        {"name": "Lalit_Huria_Profile.pdf",   "size": "250 KB",  "type": "application/pdf"},
    ],
    "kajal_mam_qvscl_intro": [
        {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB",  "type": "application/pdf"},
        {"name": "Lalit_Huria_Profile.pdf",   "size": "250 KB",  "type": "application/pdf"},
    ],
    "palak_mam_corporate_advisory": [
        {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB",  "type": "application/pdf"},
    ],
    "palak_mam_mna_fundraising": [
        {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB",  "type": "application/pdf"},
        {"name": "Lalit_Huria_Profile.pdf",   "size": "250 KB",  "type": "application/pdf"},
    ],
}

# Default attachments for AI-generated or unknown templates
_DEFAULT_ATTACHMENTS = [
    {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB",  "type": "application/pdf"},
    {"name": "Lalit_Huria_Profile.pdf",   "size": "250 KB",  "type": "application/pdf"},
]

def _get_template_attachments(template_name: Optional[str]) -> list:
    """Return the correct attachment metadata list for the given template name."""
    if not template_name:
        return _DEFAULT_ATTACHMENTS
    return TEMPLATE_ATTACHMENT_MAP.get(template_name, _DEFAULT_ATTACHMENTS)

@router.get("/pending-drafts")
@router.get("/emails")
def get_pending_drafts(page: int = 1, status: Optional[str] = None, region: Optional[str] = None, geo: Optional[str] = None, company: Optional[str] = None, name: Optional[str] = None, per_page: int = 60, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        uid = normalize_user_id(user_id) if user_id else None

        # Try Redis cache first
        cache_key = None
        if redis_available and redis_client and not any([region, geo, company, name]):
            cache_key = f"pending_drafts:{uid or 'all'}:{status or 'all'}:{page}:{per_page}"
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as ce:
                logger.warning(f"WARNING: Redis pending drafts cache read error: {ce}")

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Secure admin check using database role
        is_admin = False
        if uid:
            try:
                cur.execute("SELECT role FROM users WHERE id = %s", (int(uid),))
                role_row = cur.fetchone()
                if role_row:
                    role_val = role_row['role'] if isinstance(role_row, dict) else role_row[0]
                    if role_val and str(role_val).upper() == 'ADMIN':
                        is_admin = True
            except Exception as role_err:
                logger.warning(f"Role check failed for uid={uid}: {role_err}")

        logger.info(f"GET_PENDING_DRAFTS: header_user_id={user_id}, normalized_uid={uid}, is_admin={is_admin}")

        # Base condition
        where_clause = "WHERE email_draft IS NOT NULL"
        params = []
        
        # Show all drafts for admin users; filter by user_id for regular users
        if uid and not is_admin:
            where_clause += " AND (user_id = %s OR user_id::text = %s)"
            try:
                params.extend([int(uid), str(uid)])
            except:
                params.extend([uid, uid])
        # If user is admin or uid not provided, show all drafts without user filter

        if status:
            where_clause += " AND email_status = %s"
            params.append(status)

        if region:
            if region == 'US':
                where_clause += " AND country IN ('USA', 'US', 'United States', 'Canada')"
            elif region == 'EU':
                where_clause += " AND country IN ('UK', 'Germany', 'France', 'Spain', 'Italy', 'Netherlands', 'Sweden')"
            elif region == 'APAC':
                where_clause += " AND country IN ('India', 'Singapore', 'Australia', 'Japan', 'China')"

        if geo:
            tier1_countries = ('USA', 'US', 'Canada', 'UK', 'Germany', 'France', 'Australia', 'Japan')
            if geo == 'Tier1':
                where_clause += f" AND country IN {tier1_countries}"
            elif geo == 'Emerging':
                where_clause += f" AND country NOT IN {tier1_countries}"

        if company:
            where_clause += " AND (company_name ILIKE %s OR family_office_name ILIKE %s)"
            params.extend([f"%{company}%", f"%{company}%"])

        if name:
            where_clause += " AND (first_name ILIKE %s OR last_name ILIKE %s)"
            params.extend([f"%{name}%", f"%{name}%"])

        query = f"""
            SELECT lr.id, lr.first_name, lr.last_name, lr.email, lr.email_draft, lr.email_status,
                   lr.company_name, lr.family_office_name, lr.persona, lr.fit_score, lr.updated_at,
                   lr.email_approved_by, lr.scheduled_at, lr.user_id,
                   lr.draft_template_used,
                   u.full_name as team_member_name, u.username as team_member_username
            FROM leads_raw lr
            LEFT JOIN users u ON lr.user_id = u.id
            {where_clause}
            ORDER BY COALESCE(lr.updated_at, lr.created_at) DESC LIMIT %s OFFSET %s
        """
        params.extend([per_page, (page - 1) * per_page])

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        # count total
        count_query = f"SELECT COUNT(*) FROM leads_raw {where_clause}"
        cur.execute(count_query, tuple(params[:-2])) # exclude limit/offset
        total = cur.fetchone()[0]
        
        cur.close()
        conn.close()

        # Helper: extract company name with domain fallback
        def _company_from_email(email, company_name, family_office_name):
            if company_name:
                return company_name
            if family_office_name:
                return family_office_name
            if email and "@" in email:
                domain = email.split("@")[-1].split(".")[0].lower()
                generic = {"gmail", "yahoo", "hotmail", "outlook", "protonmail", "icloud", "qvscl", "me", "live", "microsoft", "samsung", "sea"}
                if domain not in generic:
                    return domain.capitalize()
            return None

        drafts = []
        backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
        # Pre-fetch sender profile once to avoid N+1 database queries
        profile = get_sender_profile(user_id)
        for r in rows:
            draft_content = r["email_draft"] or ""
            # Apply healing with pre-fetched profile
            draft_content = heal_draft_content(draft_content, user_id, profile)
            # Normalize literal \\n to real newlines for consistent parsing
            draft_content = draft_content.replace("\\n", "\n").replace("\\r\\n", "\n")
                
            subject = ""
            body = draft_content
            if "Subject: " in draft_content:
                # First split by double newline to separate subject line from body
                parts = draft_content.split("\n\n", 1)
                # If no double newline, maybe it's just a single newline after Subject:
                if len(parts) == 1:
                    parts = draft_content.split("\n", 1)
                    
                subject = parts[0].replace("Subject: ", "").strip()
                if len(parts) > 1:
                    body = parts[1].strip()
            elif "Subject:" in draft_content:
                # Handle missing space after Subject:
                parts = draft_content.split("\n\n", 1)
                if len(parts) == 1:
                    parts = draft_content.split("\n", 1)
                subject = parts[0].replace("Subject:", "").strip()
                if len(parts) > 1:
                    body = parts[1].strip()
                    
            # Only use the team member name for metadata, the actual lead name should come from the lead's profile.
            team_member_name = r.get("team_member_name") or r.get("team_member_username")
            lead_display_name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()

            drafts.append({
                "id": r["id"],
                "lead_id": r["id"],
                "lead_name": lead_display_name if lead_display_name else "Contact",
                "lead_email": r["email"],
                "company_name": _company_from_email(r["email"], r["company_name"], r["family_office_name"]),
                "persona": r["persona"],
                "fit_score": r.get("fit_score", 0),
                "subject": subject,
                "body": body.replace("[[BACKEND_URL]]", backend_url),
                "html_body": markdown_to_html(body.replace("[[BACKEND_URL]]", backend_url)),
                "attachments": _get_template_attachments(r.get("draft_template_used")),
                "draft_template_used": r.get("draft_template_used") or "",
                "status": r["email_status"] or "PENDING_APPROVAL",
                "performance": {"opens": 0, "clicks": 0},
                "verifier": r.get("email_approved_by") or ("admin" if r["email_status"] in ["APPROVED", "SENT"] else None),
                "updated_at": r.get("updated_at", "").isoformat() if r.get("updated_at") and hasattr(r.get("updated_at"), 'isoformat') else str(r.get("updated_at")) if r.get("updated_at") else "",
                "scheduled_at": r.get("scheduled_at").isoformat() + "Z" if r.get("scheduled_at") and hasattr(r.get("scheduled_at"), 'isoformat') else str(r.get("scheduled_at")) if r.get("scheduled_at") else ""
            })

        result = {
            "drafts": drafts,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }

        # Cache the result in Redis (short TTL of 10s for review queue)
        if cache_key and redis_available and redis_client:
            try:
                redis_client.setex(cache_key, 10, json.dumps(result))
            except Exception as ce:
                logger.warning(f"WARNING: Redis pending drafts cache write error: {ce}")

        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Return error nicely instead of 500
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e) + "\n" + traceback.format_exc())

class RefineRequest(BaseModel):
    instruction: str
    body: Optional[str] = None
    subject: Optional[str] = None

@router.post("/refine-email/{draft_id}")
def refine_email_endpoint(draft_id: int, req: RefineRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        # Get lead info to provide context to LLM
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if user_id and user_id.lower() != "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (draft_id, user_id))
        elif user_id and user_id.lower() == "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s", (draft_id,))
        else:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id IS NULL", (draft_id,))
            
        lead = cur.fetchone()

        if not lead:
            return {"error": "Lead not found"}
            
        profile = get_sender_profile(user_id)
        generator = EmailGenerator()
        refined_data = generator.refine_email(req.subject, req.body, req.instruction)
        # Inject professional signature (ensures it's present and correct after refinement)
        full_body = inject_signature(refined_data['body'], profile, draft_id)
        new_content = f"Subject: {refined_data['subject']}\n\n{full_body}"
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE leads_raw SET email_draft = %s, updated_at = NOW() WHERE id = %s", (new_content, draft_id))
        conn.commit()
        cur.close()
        conn.close()

        # --- Update or Create Gmail Draft ---
        try:
            from app.services.google_service import get_gmail_service
            import base64
            from email.mime.text import MIMEText
            
            uid = normalize_user_id(user_id)
            service = get_gmail_service(int(uid))
            if service:
                message = MIMEText(full_body, 'plain')
                message['to'] = lead.get('email', '')
                message['subject'] = refined_data['subject']
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                
                draft_body_payload = {'message': {'raw': raw_message}}
                existing_draft_id = lead.get('gmail_draft_id')
                
                if existing_draft_id:
                    # Update existing Gmail draft
                    service.users().drafts().update(userId='me', id=existing_draft_id, body=draft_body_payload).execute()
                    logger.info(f"✅ Updated Gmail draft {existing_draft_id} for Lead {draft_id}")
                else:
                    # No existing draft → create a new one and save the ID
                    created = service.users().drafts().create(userId='me', body=draft_body_payload).execute()
                    new_draft_id = created.get('id')
                    conn3 = get_db_connection()
                    cur3 = conn3.cursor()
                    cur3.execute("UPDATE leads_raw SET gmail_draft_id = %s WHERE id = %s", (new_draft_id, draft_id))
                    conn3.commit()
                    cur3.close()
                    conn3.close()
                    logger.info(f"✅ Created new Gmail draft {new_draft_id} for Lead {draft_id} during refinement")
        except Exception as ge:
            logger.warning(f"⚠️  Gmail draft update failed (non-blocking): {ge}")
        
        return {
            "subject": refined_data["subject"],
            "body": full_body
        }
        
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/approve-draft/{draft_id}")
@router.post("/approve-email/{draft_id}")
def approve_draft(draft_id: int, req: Optional[ApproveRequest] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        if not check_daily_email_limit(user_id, 1):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Daily Limit Exceeded: Sending this email would exceed your daily limit of 2000 emails. Please wait for the daily reset.")
        from app.services.email_service import send_email
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Fetch User Data for Sender Identity
        sender_email = None
        sender_name = "the team"
        current_uid = normalize_user_id(user_id)
        
        if user_id:
            cur.execute("SELECT email, full_name, username, google_id, job_title, phone, linkedin_url FROM users WHERE id = %s", (current_uid,))
            u = cur.fetchone()
            if u:
                sender_email = u['email']
                sender_name = u['full_name'] or u['username'] or "the team"
                # Crucial: Verify Google Link
                if not u['google_id']:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=400, detail="Gmail Not Connected. Please go to Settings and link your Google account to send emails from your own address.")

        # 2. Fetch/Prepare Draft
        cur.execute("SELECT first_name, last_name, email, email_draft, cc_email, draft_template_used FROM leads_raw WHERE id = %s", (draft_id,))
        lead = cur.fetchone()
        if not lead:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Lead not found")

        draft_content = lead.get('email_draft')
        draft_content = heal_draft_content(draft_content, user_id)
        email = lead.get('email')
        stored_cc = lead.get('cc_email')
        
        if not email:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Missing recipient email address for this lead.")
        
        if not draft_content:
            from app.services.llm_services import EmailGenerator
            generator = EmailGenerator()
            email_data = generator.generate_email(dict(lead), sender_name=sender_name)
            subject = email_data.get("subject", "Following up")
            body = email_data.get("body", "Hello, we would love to connect.")
            draft_content = f"Subject: {subject}\n\n{body}"
        
        # 3. Parse subject ONLY from the first line — never scan the body for 'Subject:'
        # This prevents a body that mentions 'Subject:' from overwriting the real subject.
        subject = "Following up"  # Default fallback
        body = draft_content
        
        first_line = draft_content.split("\n")[0].strip()
        if first_line.startswith("Subject:"):
            subject = first_line[len("Subject:"):].strip()
            # Body is everything after the first line (skip the blank separator too)
            rest = draft_content.split("\n", 1)
            body = rest[1].lstrip("\n").strip() if len(rest) > 1 else ""
        else:
            body = draft_content.strip()

        # Real Dispatch — Gmail API if connected, else Resend/SMTP
        uid = normalize_user_id(user_id)
        logging.info(f"Triggering real email dispatch for lead {draft_id} from {sender_email} (User: {uid})")
        
        # Check if user has Gmail connected (so we can log correctly)
        has_gmail = False
        try:
            from app.services.google_service import get_gmail_service
            svc = get_gmail_service(int(uid)) if uid else None
            has_gmail = svc is not None
        except:
            pass
        
        cc_email = req.cc if (req and req.cc) else stored_cc
        
        # --- Re-inject Signature of the CURRENT logged-in user ---
        # Only for templates without embedded SIG_START/SIG_END markers.
        # Templates like ayush_sir_hospital_draft have their own complete
        # signature block with banner image and custom disclaimer.
        profile = {
            "full_name": sender_name,
            "job_title": "Analyst", # Default if not found
            "phone": "8527083798", # Default if not found
            "linkedin_url": "https://www.linkedin.com/company/qvscl/"
        }
        
        # Try to get more details from profile
        if u:
            profile["job_title"] = u.get('job_title') or profile["job_title"]
            profile["phone"] = u.get('phone') or profile["phone"]
            profile["linkedin_url"] = u.get('linkedin_url') or profile["linkedin_url"]
        
        # Skip signature re-injection for templates with embedded SIG_START/SIG_END markers
        # to preserve their custom banner image, disclaimer, and formatting
        if "SIG_START" in body or "SIG_END" in body:
            # Just replace sender placeholders with current user's info
            body = body.replace("***{{Sender Name}}***", profile["full_name"])
            body = body.replace("{{Sender Title}}", profile["job_title"])
            body = body.replace("{{Sender Phone}}", profile["phone"])
            body = body.replace("{{Sender LinkedIn}}", profile["linkedin_url"])
            body = body.replace("{{Sender Linkedin}}", profile["linkedin_url"])
        else:
            body = inject_signature(body, profile, draft_id)
        
        template_name = lead.get('draft_template_used') if lead else None
        success, error_msg, new_thread_id, new_rfc_message_id = send_email(
            to_email=email,
            subject=subject,
            html_content=markdown_to_html(body),
            from_email=sender_email,
            from_name=sender_name,
            lead_id=draft_id,
            user_id=int(uid),
            cc=cc_email,
            template_name=template_name
        )
        
        dispatch_method = "Gmail API" if has_gmail else "Resend/SMTP"

        if success:
            # Fetch gmail_draft_id before updating the row
            cur.execute("SELECT gmail_draft_id FROM leads_raw WHERE id = %s", (draft_id,))
            draft_row = cur.fetchone()
            gmail_draft_id = draft_row['gmail_draft_id'] if draft_row else None

            # 4. Update Status and Initialize Follow-up Sequence
            cur.execute("""
                UPDATE leads_raw 
                SET email_status = 'SENT', 
                    email_approved_by = %s,
                    updated_at = NOW(),
                    last_outreach_at = NOW(),
                    followup_status = 'ACTIVE',
                    followup_stage = 0,
                    is_responded = FALSE,
                    gmail_draft_id = NULL,
                    last_outreach_subject = %s,
                    first_outreach_subject = COALESCE(first_outreach_subject, %s),
                    first_outreach_at = COALESCE(first_outreach_at, NOW()),
                    gmail_thread_id = %s,
                    gmail_message_id = %s
                WHERE id = %s
            """, (sender_name, subject, subject, new_thread_id, new_rfc_message_id, draft_id))
            conn.commit()

            # --- Delete Gmail Draft from real Gmail ---
            if gmail_draft_id:
                try:
                    from app.services.google_service import delete_gmail_draft
                    delete_gmail_draft(int(uid), gmail_draft_id)
                    logger.info(f"🗑️  Deleted Gmail draft {gmail_draft_id} for Lead {draft_id} after send")
                except Exception as ge:
                    logger.warning(f"⚠️  Failed to delete Gmail draft after send (non-blocking): {ge}")

            invalidate_pending_drafts_cache(str(uid))
            from app.models.lead import add_activity_log
            add_activity_log(draft_id, "EMAIL_SENT", f"Email dispatched via {dispatch_method} from {sender_email} — Will appear in Gmail Sent folder" if has_gmail else f"Email dispatched via {dispatch_method} from {sender_email}", sender_name)
            cur.close()
            conn.close()
            return {"status": "sent", "message": f"Success: Email dispatched to {email}"}
        else:
            conn.rollback()
            cur.close()
            conn.close()
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Outreach dispatch failed: {error_msg}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error during approval: {str(e)}")


@router.post("/reject-email/{draft_id}")
def reject_draft(draft_id: int, req: Optional[RejectRequest] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor()
    
    if user_id and user_id.lower() != "admin":
        where_clause = "WHERE id = %s AND user_id = %s"
        params = (draft_id, user_id)
    elif user_id and user_id.lower() == "admin":
        where_clause = "WHERE id = %s"
        params = (draft_id,)
    else:
        where_clause = "WHERE id = %s AND user_id IS NULL"
        params = (draft_id,)
    
    cur.execute(
        f"UPDATE leads_raw SET email_status = 'REJECTED', updated_at = NOW() {where_clause}",
        params
    )

    conn.commit()
    cur.close()
    conn.close()
    
    invalidate_pending_drafts_cache(user_id)
    from app.models.lead import add_activity_log
    add_activity_log(draft_id, "EMAIL_REJECTED", f"Reason: {req.rejected_reason if req else ''}", "admin")
    
    return {"status": "rejected", "message": "Draft rejected"}

@router.post("/schedule-email/{draft_id}")
def schedule_email(draft_id: int, req: ScheduleRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        user_clause = ""
        params = [req.scheduled_at, draft_id]
        if user_id and user_id.lower() != "admin":
            user_clause = " AND user_id = %s"
            params.append(user_id)
        elif user_id and user_id.lower() == "admin":
            pass
        else:
            user_clause = " AND user_id IS NULL"
            
        cur.execute(
            f"UPDATE leads_raw SET email_status = 'SCHEDULED', scheduled_at = %s, updated_at = NOW() WHERE id = %s {user_clause}",
            tuple(params)
        )
        conn.commit()
        from app.models.lead import add_activity_log
        add_activity_log(draft_id, "EMAIL_SCHEDULED", f"Email scheduled for {req.scheduled_at}", get_user_name(user_id))
        invalidate_pending_drafts_cache(user_id)
        cur.close()
        conn.close()
        return {"status": "scheduled", "message": f"Draft scheduled for {req.scheduled_at}"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/emails/bulk-schedule")
def bulk_schedule_emails(req: BulkScheduleRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if not req.lead_ids:
             return {"message": "No leads provided"}
             
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        where_params = [req.scheduled_at] + list(req.lead_ids)
        
        user_clause = ""
        if user_id and user_id.lower() != "admin":
            user_clause = " AND user_id = %s"
            where_params.append(user_id)
        elif user_id and user_id.lower() == "admin":
            pass
        else:
            user_clause = " AND user_id IS NULL"
            
        cur.execute(
            f"UPDATE leads_raw SET email_status = 'SCHEDULED', scheduled_at = %s, updated_at = NOW() WHERE id IN ({format_strings}) {user_clause}",
            tuple(where_params)
        )
        conn.commit()
        from app.models.lead import add_activity_log
        for lid in req.lead_ids:
            add_activity_log(lid, "EMAIL_SCHEDULED", f"Email scheduled for {req.scheduled_at}", get_user_name(user_id))
            
        cur.close()
        conn.close()
        return {"message": f"Successfully scheduled {len(req.lead_ids)} emails for {req.scheduled_at}"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/approve-bulk-domain-drafts")
def approve_bulk_domain_drafts(req: BulkDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        if user_id and user_id.lower() != "admin":
            where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s"
            params = tuple(req.lead_ids) + (uid,)
        elif user_id and user_id.lower() == "admin":
            where_clause = f"WHERE id IN ({format_strings})"
            params = tuple(req.lead_ids)
        else:
            where_clause = f"WHERE id IN ({format_strings}) AND user_id IS NULL"
            params = tuple(req.lead_ids)
        
        cur.execute(f"SELECT * FROM leads_raw {where_clause}", params)

        leads = cur.fetchall()
        
        # Group leads
        groups = {}
        for row in leads:
            lead_dict = dict(row)
            domain = lead_dict.get('domain')
            company = lead_dict.get('company_name')
            group_key = domain if domain else (company if company else str(lead_dict['id']))
            group_key = group_key.lower().strip()
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(lead_dict)
            
        total_leads_updated = 0
        total_groups = len(groups)
        
        from app.models.lead import add_activity_log
        from app.services.llm_services import EmailGenerator
        generator = EmailGenerator()
        
        for key, group_leads in groups.items():
            first_lead = group_leads[0]
            group_ids = [l['id'] for l in group_leads]
            id_format = ','.join(['%s'] * len(group_ids))
            
            # If ANY lead in group has no draft, ensure we have one to apply
            # Or if the first lead has no draft, generate it
            email_content = first_lead.get("email_draft")
            if not email_content:
                email_data = generator.generate_email(normalize_lead(first_lead))
                subject = email_data.get("subject", "Following up")
                body = email_data.get("body", "Hello, we would love to connect.")
                
                lines = body.split('\n')
                if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
                    lines = lines[1:]
                clean_body = '\n'.join(lines).lstrip()
                email_content = f"Subject: {subject}\n\nHi {{first_name}},\n\n{clean_body}"
            
            cur.execute(f"""
                UPDATE leads_raw 
                SET email_draft = CASE 
                    WHEN email_draft IS NULL THEN REPLACE(%s, '{{first_name}}', COALESCE(NULLIF(first_name, ''), 'there'))
                    ELSE email_draft 
                END,
                email_status = 'APPROVED', 
                cc_email = COALESCE(%s, cc_email),
                updated_at = NOW() 
                WHERE id IN ({id_format})
            """, (email_content, req.cc, *group_ids))
            
            # Log one activity per group/domain
            add_activity_log(None, "BULK_DOMAIN_APPROVE", f"Approved drafts for domain/group {key} ({len(group_ids)} leads)", "admin")
            
            total_leads_updated += len(group_ids)
            
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "message": f"Approved {total_groups} distinct domain draft groups ({total_leads_updated} leads).",
            "groups_processed": total_groups,
            "leads_updated": total_leads_updated
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/send-approved-batch")
def send_approved_batch(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    from app.services.email_service import send_email
    from app.api.drafts import heal_draft_content
    from app.models.lead import add_activity_log
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # 1. Fetch User Data for Sender Identity
    sender_email = None
    sender_name = "the team"
    if user_id:
        cur.execute("SELECT email, full_name, username FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        if u:
            sender_email = u['email']
            sender_name = u['full_name'] or u['username']

    # Pre-fetch sender profile once for all heal_draft_content calls
    from app.api.drafts import get_sender_profile
    profile = get_sender_profile(user_id)

    # 2. Get all approved leads for THIS user
    where_clause = "WHERE email_status = 'APPROVED'"
    params = []
    if user_id and user_id.lower() != "admin":
        where_clause += " AND user_id = %s"
        params.append(user_id)
    elif user_id and user_id.lower() == "admin":
        pass
    else:
        where_clause += " AND user_id IS NULL"
    
    cur.execute(f"SELECT id, email, email_draft, cc_email FROM leads_raw {where_clause}", params)
    leads_to_send = cur.fetchall()
    
    if leads_to_send and not check_daily_email_limit(user_id, len(leads_to_send)):
        cur.close()
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Daily Limit Exceeded: Sending this batch would exceed your daily limit of 2000 emails. Please wait for the daily reset.")
    
    sent_count = 0
    for lead in leads_to_send:
        try:
            draft_content = lead['email_draft'] or ""
            draft_content = heal_draft_content(draft_content, user_id, profile)
            
            subject = "Following up"
            body = draft_content
            if "Subject: " in draft_content:
                parts = draft_content.split("\n\n", 1)
                subject = parts[0].replace("Subject: ", "").strip()
                body = parts[1].strip() if len(parts) > 1 else ""

            uid_val = normalize_user_id(user_id)
            success, error_msg, new_thread_id, new_rfc_message_id = send_email(
                to_email=lead['email'],
                subject=subject,
                html_content=markdown_to_html(body),
                from_email=sender_email,
                from_name=sender_name,
                lead_id=lead['id'],
                user_id=int(uid_val),
                cc=lead['cc_email']
            )

            if success:
                cur.execute("""
                    UPDATE leads_raw 
                    SET email_status = 'SENT', 
                        updated_at = NOW(),
                        last_outreach_at = NOW(),
                        last_outreach_subject = %s,
                        first_outreach_subject = COALESCE(first_outreach_subject, %s),
                        first_outreach_at = COALESCE(first_outreach_at, NOW()),
                        gmail_thread_id = %s,
                        gmail_message_id = %s,
                        followup_status = 'ACTIVE',
                        followup_stage = 0,
                        is_responded = FALSE
                    WHERE id = %s
                """, (subject, subject, new_thread_id, new_rfc_message_id, lead['id']))
                add_activity_log(lead['id'], "EMAIL_SENT", f"Email dispatched via Resend from {sender_email}", "system")
                sent_count += 1
        except Exception as e:
            logger.error(f"Batch dispatch error for lead {lead['id']}: {str(e)}")

    conn.commit()
    cur.close()
    conn.close()

    invalidate_pending_drafts_cache(user_id)
    
    return {"message": f"Successfully sent {sent_count} approved emails via Gmail API."}


class BulkSendRequest(BaseModel):
    lead_ids: list
    cc: Optional[str] = None

@router.post("/send-selected-batch")
def send_selected_batch(req: BulkSendRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Send emails for a specific list of lead IDs via the logged-in user's Gmail account."""
    from app.services.email_service import send_email
    from app.api.drafts import heal_draft_content
    from app.models.lead import add_activity_log
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # 1. Fetch sender info
    sender_email = None
    sender_name = "the team"
    uid = normalize_user_id(user_id)

    if uid:
        cur.execute("SELECT email, full_name, username, google_id FROM users WHERE id = %s", (uid,))
        u = cur.fetchone()
        if u:
            sender_email = u['email']
            sender_name = u['full_name'] or u['username'] or "the team"
            if not u['google_id']:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Gmail Not Connected. Please link your Google account in Settings before sending.")

    from app.api.drafts import get_sender_profile
    profile = get_sender_profile(user_id)

    # 2. Fetch the requested leads
    cur.execute(
        "SELECT id, email, email_draft, gmail_draft_id, cc_email FROM leads_raw WHERE id = ANY(%s)",
        (req.lead_ids,)
    )
    leads_to_send = cur.fetchall()
    
    if leads_to_send and not check_daily_email_limit(user_id, len(leads_to_send)):
        cur.close()
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Daily Limit Exceeded: Sending this batch would exceed your daily limit of 2000 emails. Please wait for the daily reset.")

    sent_count = 0
    failed_count = 0
    results = []

    for lead in leads_to_send:
        try:
            draft_content = lead['email_draft'] or ""
            draft_content = heal_draft_content(draft_content, user_id, profile)
            
            subject = "Following up"
            body = draft_content
            if "Subject: " in draft_content:
                parts = draft_content.split("\n\n", 1)
                subject = parts[0].replace("Subject: ", "").strip()
                body = parts[1].strip() if len(parts) > 1 else ""

            success, error_msg, new_thread_id, new_rfc_message_id = send_email(
                to_email=lead['email'],
                subject=subject,
                html_content=markdown_to_html(body),
                from_email=sender_email,
                from_name=sender_name,
                lead_id=lead['id'],
                user_id=uid,
                cc=lead['cc_email']
            )

            if success:
                cur.execute("""
                    UPDATE leads_raw 
                    SET email_status = 'SENT', 
                        email_approved_by = %s,
                        updated_at = NOW(),
                        last_outreach_at = NOW(),
                        last_outreach_subject = %s,
                        first_outreach_subject = COALESCE(first_outreach_subject, %s),
                        first_outreach_at = COALESCE(first_outreach_at, NOW()),
                        gmail_thread_id = %s,
                        gmail_message_id = %s,
                        followup_status = 'ACTIVE',
                        followup_stage = 0,
                        is_responded = FALSE,
                        gmail_draft_id = NULL
                    WHERE id = %s
                """, (sender_name, subject, subject, new_thread_id, new_rfc_message_id, lead['id']))
                add_activity_log(lead['id'], "EMAIL_SENT", f"Email dispatched via Gmail API from {sender_email} — Appears in Gmail Sent folder", sender_name)
                
                if lead.get('gmail_draft_id'):
                    try:
                        from app.services.google_service import delete_gmail_draft
                        delete_gmail_draft(int(uid), lead['gmail_draft_id'])
                    except Exception as de:
                        logger.error(f"Failed to delete draft {lead['gmail_draft_id']}: {de}")

                sent_count += 1
                results.append({"id": lead['id'], "email": lead['email'], "status": "sent"})
            else:
                failed_count += 1
                results.append({"id": lead['id'], "email": lead['email'], "status": "failed", "error": error_msg})
        except Exception as e:
            logger.error(f"Bulk send error for lead {lead['id']}: {str(e)}")
            failed_count += 1
            results.append({"id": lead['id'], "email": lead['email'], "status": "failed", "error": str(e)})

    conn.commit()
    cur.close()
    conn.close()

    invalidate_pending_drafts_cache(user_id)

    return {
        "message": f"Sent {sent_count} of {len(leads_to_send)} emails via Gmail API.",
        "sent_count": sent_count,
        "failed_count": failed_count,
        "results": results
    }


@router.post("/generate-bulk-domain-drafts")
def generate_bulk_domain_drafts(req: BulkDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        # Resolve User ID
        uid = normalize_user_id(user_id)
        from app.models.lead import get_lead_by_id
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        if user_id and user_id.lower() != "admin":
            where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s"
            params = tuple(req.lead_ids) + (uid,)
        elif user_id and user_id.lower() == "admin":
            where_clause = f"WHERE id IN ({format_strings})"
            params = tuple(req.lead_ids)
        else:
            where_clause = f"WHERE id IN ({format_strings}) AND user_id IS NULL"
            params = tuple(req.lead_ids)

        cur.execute(f"SELECT * FROM leads_raw {where_clause}", params)

        leads = cur.fetchall()
        
        # Group leads
        groups = {}
        for row in leads:
            lead_dict = dict(row)
            domain = lead_dict.get('domain')
            company = lead_dict.get('company_name')
            group_key = domain if domain else (company if company else str(lead_dict['id']))
            group_key = group_key.lower().strip()
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(lead_dict)
            
        generator = EmailGenerator()
        total_leads_updated = 0
        total_groups = len(groups)
        
        def process_group(group_key, group_leads):
            first_lead = group_leads[0]
            try:
                sender_name = get_user_name(user_id)
                email_data = generator.generate_email(normalize_lead(first_lead), sender_name=sender_name)
                subject = email_data.get("subject", "Following up")
                body = email_data.get("body", "Hello, we would love to connect.")
            except Exception as e:
                print(f"Error generating email for {group_key}: {e}")
                subject = "Following up"
                body = "Hello, we would love to connect to discuss potential synergies."
                
            lines = body.split('\n')
            if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
                lines = lines[1:]
            clean_body = '\n'.join(lines).lstrip()
            return f"Subject: {subject}\n\nHi {{first_name}},\n\n{clean_body}", group_leads
            
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_group, k, v) for k, v in groups.items()]
            for future in as_completed(futures):
                res = future.result()
                if res: results.append(res)
                
        from app.services.google_service import get_gmail_service
        import base64
        from email.mime.text import MIMEText
        
        uid_t = normalize_user_id(user_id)
        service = None
        try:
            service = get_gmail_service(int(uid_t))
            if not service:
                print(f"DEBUG: No Gmail service found for user {uid_t}. Syncing to Gmail skipped.")
        except Exception as e:
            print(f"DEBUG: Error initializing Gmail service for sync: {e}")
            pass

        for email_content, group_leads in results:
            for lead_item in group_leads:
                # Resolve content for THIS specific lead
                first_name = (lead_item.get('first_name') or '').strip() or 'there'
                resolved_content = email_content.replace('{{first_name}}', first_name)
                
                # Parse subject and body
                subject = "Following up"
                body = resolved_content
                if "Subject: " in resolved_content:
                    parts = resolved_content.split("\n\n", 1)
                    subject = parts[0].replace("Subject: ", "").strip()
                    body = parts[1].strip() if len(parts) > 1 else ""

                # Sync to Gmail if service is available
                gmail_draft_id = None
                if service:
                    try:
                        message = MIMEText(body, 'plain')
                        message['to'] = lead_item.get('email', '')
                        message['subject'] = subject
                        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                        draft_body = {'message': {'raw': raw_message}}
                        created_draft = service.users().drafts().create(userId='me', body=draft_body).execute()
                        gmail_draft_id = created_draft.get('id')
                    except Exception as ge:
                        logger.warning(f"⚠️ Gmail sync failed for lead {lead_item['id']}: {ge}")

                # Update DB
                cur.execute("""
                    UPDATE leads_raw 
                    SET email_draft = %s, 
                        email_status = 'PENDING_APPROVAL', 
                        cc_email = COALESCE(%s, cc_email),
                        updated_at = NOW(),
                        gmail_draft_id = %s
                    WHERE id = %s
                """, (resolved_content, req.cc, gmail_draft_id, lead_item['id']))
                
                total_leads_updated += 1
            
        conn.commit()
        cur.close()
        conn.close()

        # Log bulk activity
        try:
            from app.models.lead import add_activity_log
            add_activity_log(None, "BULK_DRAFT_GENERATE", f"Generated domain-wise drafts for {total_leads_updated} leads across {total_groups} groups", "admin")
        except:
            pass
        
        return {
            "message": f"Generated {total_groups} distinct domain drafts and applied to {total_leads_updated} leads.",
            "groups_processed": total_groups,
            "leads_updated": total_leads_updated
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/send-bulk-domain-emails")
def send_bulk_domain_emails(req: BulkSendRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    from app.services.email_service import send_email
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        if not check_daily_email_limit(user_id, len(req.lead_ids)):
            cur.close()
            conn.close()
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Daily Limit Exceeded: Sending this batch would exceed your daily limit of 2000 emails. Please wait for the daily reset.")
            
        # 1. Fetch User Data
        uid = normalize_user_id(user_id)
        cur.execute("SELECT email, full_name, username, job_title, phone, linkedin_url FROM users WHERE id = %s", (uid,))
        u = cur.fetchone()
        
        sender_email = u['email'] if u else None
        sender_name = (u['full_name'] or u['username']) if u else "the team"
        
        profile = {
            "full_name": sender_name,
            "job_title": (u['job_title'] if u else None) or "Analyst",
            "phone": (u['phone'] if u else None) or "8527083798",
            "linkedin_url": (u['linkedin_url'] if u else None) or "https://www.linkedin.com/company/qvscl/"
        }

        format_strings = ','.join(['%s'] * len(req.lead_ids))
        if str(user_id).lower() == "admin":
            where_clause = f"WHERE id IN ({format_strings})"
            params = tuple(req.lead_ids)
        elif uid:
            where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s"
            params = tuple(req.lead_ids) + (uid,)
        else:
            where_clause = f"WHERE id IN ({format_strings}) AND user_id IS NULL"
            params = tuple(req.lead_ids)

        cur.execute(f"SELECT id, first_name, email, email_draft, domain, company_name, cc_email FROM leads_raw {where_clause}", params)
        leads = cur.fetchall()
        
        sent_count = 0
        from app.models.lead import add_activity_log
        from app.services.llm_services import EmailGenerator
        generator = EmailGenerator()

        for lead in leads:
            try:
                # If draft already exists, use it. Otherwise generate.
                email_content = lead.get("email_draft")
                if not email_content:
                    email_data = generator.generate_email(normalize_lead(dict(lead)), sender_name=sender_name)
                    subject = email_data.get("subject", "Following up")
                    body = email_data.get("body", "Hello, we would love to connect.")
                    email_content = f"Subject: {subject}\n\n{body}"
                
                # Parse Subject and Body
                subject = "Following up"
                body = email_content
                if "Subject: " in email_content:
                    parts = email_content.split("\n\n", 1)
                    subject = parts[0].replace("Subject: ", "").strip()
                    body = parts[1].strip() if len(parts) > 1 else ""
                
                # RE-INJECT Signature of the CURRENT user
                final_body = inject_signature(body, profile, lead['id'])

                # Real Dispatch
                success, error_msg, new_thread_id, new_rfc_message_id = send_email(
                    to_email=lead['email'],
                    subject=subject,
                    html_content=markdown_to_html(final_body),
                    from_email=sender_email,
                    from_name=sender_name,
                    lead_id=lead['id'],
                    user_id=int(uid),
                    cc=req.cc or lead['cc_email']
                )

                if success:
                    cur.execute("""
                        UPDATE leads_raw 
                        SET email_draft = %s, 
                            email_status = 'SENT', 
                            updated_at = NOW(),
                            last_outreach_at = NOW(),
                            last_outreach_subject = %s,
                            first_outreach_subject = COALESCE(first_outreach_subject, %s),
                            first_outreach_at = COALESCE(first_outreach_at, NOW()),
                            gmail_thread_id = %s,
                            gmail_message_id = %s,
                            followup_status = 'ACTIVE',
                            followup_stage = 0,
                            is_responded = FALSE
                        WHERE id = %s
                    """, (email_content, subject, subject, new_thread_id, new_rfc_message_id, lead['id']))
                    add_activity_log(lead['id'], "EMAIL_SENT", f"Bulk domain email dispatched via Gmail API from {sender_email}", "system")
                    sent_count += 1
            except Exception as e:
                print(f"Error sending bulk lead {lead['id']}: {e}")

        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "message": f"Successfully sent {sent_count} emails via Resend.",
            "leads_processed": len(leads),
            "leads_sent": sent_count
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Screenshot-based Template Creator
# ---------------------------------------------------------------------------
@router.post("/analyze-template-screenshot")
async def analyze_screenshot(files: List[UploadFile] = File(..., description="Upload 1-5 screenshots of email templates. AI analyzes each and merges them into one template.")):
    """Upload up to 5 screenshots of an email template. AI analyzes each and merges them into one complete template."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images allowed")
    
    for f in files:
        if not f.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"'{f.filename}' is not an image file")
    
    merged_subject = ""
    merged_body_parts = []
    merged_notes = []
    
    for file in files:
        contents = await file.read()
        image_base64 = base64.b64encode(contents).decode("utf-8")
        result = analyze_template_screenshot(image_base64)
        
        if result.get("subject") and not merged_subject:
            merged_subject = result["subject"]
        if result.get("body"):
            merged_body_parts.append(result["body"])
        if result.get("formatting_notes"):
            merged_notes.append(result["formatting_notes"])
    
    return {
        "subject": merged_subject,
        "body": "\n\n".join(merged_body_parts) if len(merged_body_parts) > 1 else (merged_body_parts[0] if merged_body_parts else ""),
        "formatting_notes": " | ".join(merged_notes) if merged_notes else ""
    }