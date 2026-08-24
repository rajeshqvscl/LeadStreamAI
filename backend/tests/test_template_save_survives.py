"""
End-to-end regression test for the template-save bug:
1. Pick a seeded template (kajal_mam_agritech) and back up its content.
2. Simulate the user's PUT save (update_prompt with new content).
3. Call the GET /custom-draft-templates list function (what the frontend calls
   after every save via fetchPrompts()).
4. Verify the edit SURVIVES the list call (previously the force-update blocks
   reverted it instantly).
5. Also re-run the module-load seeding logic to ensure it doesn't clobber either.
6. Restore the original content.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

from app.database import get_db_connection
from app.models.prompt import update_prompt
import psycopg2.extras

TEMPLATE_NAME = "kajal_mam_agritech"
EDIT_MARKER = "USER-EDIT-TEST-MARKER-xyz123"


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT id, content FROM prompts WHERE name = %s", (TEMPLATE_NAME,))
    row = cur.fetchone()
    if not row:
        print(f"FAIL: template {TEMPLATE_NAME} not found")
        return
    tpl_id = row["id"]
    original = row["content"]

    try:
        # 1. Simulate user edit (exactly what PUT /api/prompts/{id} does)
        edit_content = original + "\n\n" + EDIT_MARKER
        ok = update_prompt(tpl_id, {"content": edit_content})
        print(f"1. PUT save applied: {ok}")

        # 2. Call the GET list function (same as frontend fetchPrompts)
        from app.api.drafts import list_custom_draft_templates
        listed = list_custom_draft_templates(user_id="3")
        listed_row = next((t for t in listed if t["id"] == tpl_id), None)
        if not listed_row:
            print("FAIL: template missing from list response")
            return
        survived_list = EDIT_MARKER in (listed_row.get("content") or "")
        print(f"2. After GET /custom-draft-templates: edit survived = {survived_list}")

        # 3. Re-check DB directly (module-load seeding also runs at import)
        cur.execute("SELECT content FROM prompts WHERE id = %s", (tpl_id,))
        db_content = cur.fetchone()["content"]
        survived_db = EDIT_MARKER in (db_content or "")
        print(f"3. DB content still has edit = {survived_db}")

        if survived_list and survived_db:
            print("\nRESULT: PASS -- template edits now survive list + seeding")
        else:
            print("\nRESULT: FAIL -- edits are still being reverted")
    finally:
        # Restore original content
        update_prompt(tpl_id, {"content": original})
        cur.close()
        conn.close()
        print("(original template content restored)")


if __name__ == "__main__":
    main()
