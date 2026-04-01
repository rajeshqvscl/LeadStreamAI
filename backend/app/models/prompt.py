import psycopg2
from app.database import get_db_connection

def get_all_prompts():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM prompts ORDER BY id ASC")
    prompts = cur.fetchall()
    cur.close()
    conn.close()
    return prompts

def get_active_prompt_by_type(prompt_type):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM prompts WHERE prompt_type = %s AND is_active = TRUE LIMIT 1", (prompt_type,))
    prompt = cur.fetchone()
    cur.close()
    conn.close()
    return prompt

def create_prompt(name, prompt_type, content, description=None, is_active=True):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO prompts (name, prompt_type, content, description, is_active)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
    """, (name, prompt_type, content, description, is_active))
    prompt_id = cur.fetchone()['id']
    conn.commit()
    cur.close()
    conn.close()
    return prompt_id

def update_prompt(prompt_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    fields = []
    values = []
    for k, v in data.items():
        if k in ['name', 'content', 'description', 'is_active', 'prompt_type']:
            fields.append(f"{k} = %s")
            values.append(v)
    
    if not fields:
        return False
        
    values.append(prompt_id)
    cur.execute(f"UPDATE prompts SET {', '.join(fields)}, updated_at = NOW() WHERE id = %s", tuple(values))
    conn.commit()
    cur.close()
    conn.close()
    return True

def delete_prompt(prompt_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM prompts WHERE id = %s", (prompt_id,))
    conn.commit()
    cur.close()
    conn.close()
    return True
