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
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    # Ensure columns exist if table was already created with old schema
    columns_to_add = [
        ("persona", "TEXT"),
        ("phone", "TEXT"),
        ("city", "TEXT"),
        ("country", "TEXT"),
        ("fit_score", "INTEGER DEFAULT 0"),
        ("validation_status", "TEXT DEFAULT 'PENDING'"),
        ("email_status", "TEXT DEFAULT 'PENDING'"),
        ("email_draft", "TEXT"),
        ("linkedin_url", "TEXT"),
        ("labels", "TEXT[] DEFAULT '{}'"),
        ("updated_at", "TIMESTAMP DEFAULT NOW()")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE leads_raw ADD COLUMN {col_name} {col_type};")
        except psycopg2.Error:
            conn.rollback()
            continue
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS family_offices (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        location TEXT,
        category TEXT,
        strategic_fit TEXT,
        last_synced TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id SERIAL PRIMARY KEY,
        lead_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        performed_by TEXT DEFAULT 'system',
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

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
    
    conn.commit()
    cur.close()
    conn.close()