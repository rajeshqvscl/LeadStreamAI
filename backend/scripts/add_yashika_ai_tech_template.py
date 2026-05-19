import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

name = "yashika_draft_ai_tech"
description = "AI-Powered Hiring Infrastructure Platform fundraising draft ($1M)"
content = """Subject: AI-Powered Hiring Infrastructure Platform Company | 100K+ Recruiters | 250+ Companies |

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

def add_template():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print(f"Checking if template '{name}' already exists...")
    cur.execute("SELECT id FROM prompts WHERE name = %s;", (name,))
    existing = cur.fetchone()

    if existing:
        print(f"Template '{name}' already exists (id={existing[0]}). Updating content...")
        cur.execute(
            "UPDATE prompts SET content = %s, description = %s WHERE name = %s;",
            (content, description, name)
        )
    else:
        print(f"Inserting new template '{name}'...")
        cur.execute(
            "INSERT INTO prompts (name, description, content, prompt_type) VALUES (%s, %s, %s, %s);",
            (name, description, content, "CUSTOM_DRAFT")
        )

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Done. Template '{name}' is ready.")

if __name__ == "__main__":
    add_template()
