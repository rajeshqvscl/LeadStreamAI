import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.database import get_db_connection
import psycopg2.extras

TEMPLATE_NAME = "palak_mam_Draft_1"
TEMPLATE_TYPE = "CUSTOM_DRAFT"
TEMPLATE_DESC = "M&A / Strategic Partnership outreach template by Palak Jain"
TEMPLATE_CONTENT = """Dear {{First Name}},

**Greetings from QVSCL.**

I'll keep this brief — we are currently working with multiple businesses actively exploring **M&A, strategic partnerships, and acquisition opportunities** to accelerate growth and strengthen market positioning.

If you are:
Looking to **Acquire a company in India** to expand capabilities or enter new markets
Exploring a **Strategic merger or Joint Venture in India**
Evaluating **Growth through inorganic routes**
—We can support you end-to-end, including:
Identifying and evaluating relevant targets/opportunities
Valuation and deal structuring
Managing diligence and negotiations
Ensuring smooth transaction closure and integration
**We bring a hands-on, confidential approach backed by strong market access across sectors.** If this is relevant, I'm happy to schedule a quick discussion and share live opportunities currently in the market. I am sharing our Company Profile attached to this email for your reference.

Looking forward to connecting.

SIG_START
--
Thanks & Regards,
Palak Jain,
Business Development Associate,
SIG_LINK_LABEL:Add me on LinkedIn:https://www.linkedin.com/in/palak-jain-057b47229/
9520372034
SIG_END"""


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Check if already exists
    cur.execute("SELECT id FROM prompts WHERE name = %s", (TEMPLATE_NAME,))
    existing = cur.fetchone()

    if existing:
        # Update it
        cur.execute("""
            UPDATE prompts SET content = %s, description = %s, prompt_type = %s, is_active = TRUE, updated_at = NOW()
            WHERE name = %s
        """, (TEMPLATE_CONTENT, TEMPLATE_DESC, TEMPLATE_TYPE, TEMPLATE_NAME))
        print(f"Updated existing prompt: {TEMPLATE_NAME} (id={existing['id']})")
    else:
        cur.execute("""
            INSERT INTO prompts (name, prompt_type, content, description, is_active)
            VALUES (%s, %s, %s, %s, TRUE) RETURNING id
        """, (TEMPLATE_NAME, TEMPLATE_TYPE, TEMPLATE_CONTENT, TEMPLATE_DESC))
        new_id = cur.fetchone()['id']
        print(f"Inserted new prompt: {TEMPLATE_NAME} (id={new_id})")

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
