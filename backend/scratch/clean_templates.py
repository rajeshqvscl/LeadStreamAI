# scratch/clean_templates.py
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def clean():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Fetch all custom draft templates
    cur.execute("SELECT id, content FROM prompts WHERE prompt_type = 'CUSTOM_DRAFT'")
    prompts = cur.fetchall()
    
    for pid, content in prompts:
        if not content: continue
        
        # Remove SIG_START/SIG_END tags
        new_content = content.replace("SIG_START", "").replace("SIG_END", "")
        
        # Detect if there's a hardcoded sign-off at the end and remove it to avoid double-sign-off
        # We want the system to handle the signature centrally
        sign_offs = ["Thanks & Regards", "Sincerely", "Best regards", "--"]
        lines = new_content.strip().split("\n")
        clean_lines = lines[:]
        
        found_signoff = False
        for i in range(len(lines) - 1, max(-1, len(lines) - 15), -1):
            line = lines[i].strip()
            if any(line.startswith(s) for s in sign_offs) or (len(line) > 0 and line in ["Palak Jain,", "Yashika Gupta,", "sravanthi"]):
                clean_lines = lines[:i]
                found_signoff = True
                break
        
        if found_signoff:
            final_content = "\n".join(clean_lines).strip()
            print(f"Cleaning template {pid}...")
            cur.execute("UPDATE prompts SET content = %s WHERE id = %s", (final_content, pid))
    
    conn.commit()
    cur.close()
    conn.close()
    print("Done cleaning templates.")

if __name__ == "__main__":
    clean()
