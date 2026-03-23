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
        email TEXT,
        first_name TEXT,
        last_name TEXT,
        company_name TEXT,
        domain TEXT,
        source TEXT,
        raw_payload JSONB,
        family_office_name TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

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
    
    conn.commit()
    cur.close()
    conn.close()