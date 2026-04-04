import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

# Create Database Tables
def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads_raw (
        id SERIAL PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        email TEXT UNIQUE,
        domain TEXT,
        linkedin_url TEXT,
        company_name TEXT,
        persona TEXT,
        phone TEXT,
        city TEXT,
        country TEXT,
        source TEXT,
        raw_payload JSONB,
        fit_score INTEGER DEFAULT 0,
        validation_status TEXT DEFAULT 'PENDING',
        email_status TEXT DEFAULT 'PENDING',
        email_draft TEXT,
        family_office_name TEXT,
        labels TEXT[] DEFAULT '{}',
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    # Ensure columns exist if table was already created with old schema
    columns_to_add = [
        ("persona", "TEXT"),
        ("phone", "TEXT"),
        ("city", "TEXT"),
        ("country", "TEXT"),
        ("designation", "TEXT"),
        ("fit_score", "INTEGER DEFAULT 0"),
        ("validation_status", "TEXT DEFAULT 'PENDING'"),
        ("email_status", "TEXT DEFAULT 'PENDING'"),
        ("email_draft", "TEXT"),
        ("linkedin_url", "TEXT"),
        ("labels", "TEXT[] DEFAULT '{}'"),
        ("user_id", "INTEGER"),
        ("updated_at", "TIMESTAMP DEFAULT NOW()")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE leads_raw ADD COLUMN {col_name} {col_type};")
        except psycopg2.Error:
            conn.rollback()
            continue
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id SERIAL PRIMARY KEY,
        lead_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        performed_by TEXT DEFAULT 'system',
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    # Ensure user_id exists in activity_log
    try:
        cur.execute("ALTER TABLE activity_log ADD COLUMN user_id INTEGER;")
    except psycopg2.Error:
        conn.rollback()


    # Campaigns Feature Tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        tone TEXT DEFAULT 'professional',
        target_industry TEXT,
        target_persona TEXT,
        subject TEXT,
        html_body TEXT,
        context_prompt TEXT,
        strategy_prompt TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recipients (
        id SERIAL PRIMARY KEY,
        campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
        lead_id INTEGER REFERENCES leads_raw(id) ON DELETE CASCADE,
        status TEXT DEFAULT 'PENDING',
        tracking_token TEXT UNIQUE NOT NULL,
        sent_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaign_events (
        id SERIAL PRIMARY KEY,
        campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
        recipient_id INTEGER REFERENCES recipients(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL, -- SENT, OPEN, CLICK, UNSUBSCRIBE
        ip_address TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    # Users Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT,
        password_hash TEXT,
        role TEXT DEFAULT 'USER',
        is_active BOOLEAN DEFAULT TRUE,
        is_approved BOOLEAN DEFAULT FALSE,
        has_db_access BOOLEAN DEFAULT FALSE,
        google_id TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    # Ensure columns exist in users (schema evolution)
    user_cols = [
        ("is_approved", "BOOLEAN DEFAULT FALSE"),
        ("has_db_access", "BOOLEAN DEFAULT FALSE"),
        ("google_id", "TEXT"),
        ("email", "TEXT UNIQUE")
    ]
    for col_name, col_type in user_cols:
        try:
            # PostgreSQL 9.6+ supports IF NOT EXISTS for ADD COLUMN
            cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
            conn.commit() # Commit each change to be safe
        except psycopg2.Error:
            conn.rollback()
            continue

    # Family Offices Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS family_offices (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        location TEXT,
        category TEXT,
        strategic_fit TEXT,
        last_synced TIMESTAMP,
        user_id INTEGER
    );
    """)

    # Prompts Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS prompts (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        prompt_type TEXT NOT NULL,
        content TEXT NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)

    # Seed default prompts if table is empty
    cur.execute("SELECT COUNT(*) FROM prompts")
    if cur.fetchone()['count'] == 0:
        default_prompts = [
            ("Default Classification Prompt", "CLASSIFICATION", 
             "You are a lead classification expert. Analyze the following lead information and classify them.\n\nLead Information:\n- Name: {{name}}\n- Email: {{email}}\n- Designation/Title: {{designation}}\n- Company: {{company_name}}\n- Industry: {{industry}}\n- LinkedIn: {{linkedin}}",
             "Default prompt for classifying leads by persona and company type."),
            
            ("Default Email Generation Prompt", "EMAIL_GENERATION",
             "- Tone: {{tone}}\n- Sector Context: {{context}}\n- Be concise (under 200 words for body)\n\nRespond in valid JSON format:\n{\n  \"subject\": \"email subject line\",\n  \"body\": \"full email body in plain text\"\n}",
             "Default prompt for generating outreach emails."),
            
            ("Default Strategy Prompt", "STRATEGY",
             "Focus on building genuine connections. Lead with value, not sales pitch. Mention specific industry trends when possible. Keep the tone consultative.",
             "Default strategy guidelines for email generation."),
            
            ("Default Context Prompt", "CONTEXT",
             "We are a technology company that helps businesses automate their workflows and improve operational efficiency through AI-powered solutions.",
             "Default company context for emails.")
        ]
        for name, p_type, content, desc in default_prompts:
            cur.execute("""
                INSERT INTO prompts (name, prompt_type, content, description, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (name, p_type, content, desc))

    # Seed default admin if missing
    cur.execute("SELECT COUNT(*) FROM users WHERE username = %s", (os.getenv("ADMIN_USERNAME", "admin"),))
    if cur.fetchone()['count'] == 0:
        import hashlib
        # Default credentials for first setup
        default_username = os.getenv("ADMIN_USERNAME", "admin")
        default_password = os.getenv("ADMIN_PASSWORD", "admin123")
        password_hash = hashlib.sha256(default_password.encode()).hexdigest()
        
        cur.execute("""
            INSERT INTO users (username, email, full_name, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (default_username, "admin@leadstreamai.com", "System Administrator", password_hash, "ADMIN"))
    
    
    conn.commit()
    cur.close()
    conn.close()

    # Auto-sync family offices from Google Sheets on startup if table is empty
    try:
        import requests as req_lib
        sheet_url = os.getenv("FAMILY_OFFICES_PATH")
        if sheet_url:
            conn2 = get_db_connection()
            cur2 = conn2.cursor()
            cur2.execute("SELECT COUNT(*) FROM family_offices")
            fo_count = cur2.fetchone()['count']
            cur2.close()
            conn2.close()

            if fo_count == 0:
                doc_id = sheet_url.split('/d/')[1].split('/')[0]
                export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"
                response = req_lib.get(export_url, timeout=15)
                if response.ok:
                    from app.models.family_office import sync_from_csv
                    sync_from_csv(response.text)
                    print(f"[startup] Auto-synced family offices from Google Sheets.")
    except Exception as e:
        print(f"[startup] Could not auto-sync family offices: {e}")
