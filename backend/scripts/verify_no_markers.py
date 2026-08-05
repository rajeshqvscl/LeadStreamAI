"""Verify no test markers remain in prompts + no unguarded seed UPDATEs."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

from app.database import get_db_connection
import psycopg2.extras

conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute(
    "SELECT COUNT(*) as n FROM prompts WHERE content ILIKE '%USER-EDIT-TEST-MARKER%' "
    "OR followup_1 ILIKE '%USER-EDIT-TEST-MARKER%' OR followup_2 ILIKE '%USER-EDIT-TEST-MARKER%' "
    "OR followup_3 ILIKE '%USER-EDIT-TEST-MARKER%'"
)
print("test markers in prompts:", cur.fetchone()["n"])

# Guard check: read the source, ensure every seed UPDATE has placeholder guard.
# Capture the FULL statement (through the WHERE + trailing AND clause) so the
# guard text is included.
src = Path("../backend/app/api/drafts.py").resolve().read_text(encoding="utf-8")
import re

bad = []
for m in re.finditer(r"UPDATE prompts SET (.+?;) WHERE name = '([^']+)'", src, re.DOTALL):
    stmt = m.group(1)
    tpl = m.group(2)
    # Skip the targeted disclaimer strips and owner-only seeds
    if "REPLACE" in stmt or "regexp_replace" in stmt:
        continue
    if "content" in stmt and "placeholder" not in stmt:
        bad.append(tpl)
print("unguarded content seed UPDATEs:", bad if bad else "NONE")

conn.close()
