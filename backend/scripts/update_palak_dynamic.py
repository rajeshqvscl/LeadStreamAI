import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

PALAK_CONTENT = """Subject: Strategic Investment/Partnership Opportunity | QVSCL × {{Company Name}}

Dear {{First Name}},

I hope you're having a productive week.

I'm {{Sender Name}} from QVSCL. We’ve been closely following the recruitment tech space, and I wanted to reach out regarding a high-growth **vertical AI hiring platform** we are currently advising for their **$1M fundraise**.

**Key Highlights:**
• **Proven Traction**: 250+ enterprise customers and 100K+ companies onboarded.
• **Unified Stack**: Integration of ATS, Sourcing, and Background Verification in one platform.
• **Market Need**: Solving the 1.5M workforce gap in the Indian market specifically.

We believe this could be a strategic fit for your portfolio. I’ve attached the QVSCL profile for your reference.

Would you be open to a quick 10-minute sync to discuss this further? Alternatively, I can share the pitch deck for your initial review.

SIG_START
--
**Thanks & Regards,**
*{{Sender Name}},*
**{{Sender Title}},**
[LinkedIn]({{Sender LinkedIn}})
**{{Sender Phone}}**
SIG_END
"""

def update_templates():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Update Palak's template to be dynamic and have a subject
    cur.execute(
        "UPDATE prompts SET content = %s WHERE name = 'palak_mam_Draft_1'",
        (PALAK_CONTENT,)
    )
    
    conn.commit()
    print("Palak's Template updated to be dynamic.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    update_templates()
