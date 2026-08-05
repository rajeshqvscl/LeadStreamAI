"""Final verification: confirm no SIG_START/SIG_END markers remain anywhere in the
DB, and Kajal's (user 3) signature is clean (no <br> / <span> / SIG markers)."""
import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path('app/.env'))
from app.database import get_db_connection
import psycopg2.extras

conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# 1) FULL DB scan: every text/varchar/jsonb column in every table
cur.execute(
    "SELECT table_name, column_name, data_type FROM information_schema.columns "
    "WHERE table_schema = 'public' AND data_type IN ('text', 'character varying', 'jsonb') "
    "ORDER BY table_name, column_name"
)
cols = cur.fetchall()
print(f'Scanning {len(cols)} text columns across all tables for SIG_START/SIG_END...')
hits = 0
for c in cols:
    t, col, dt = c['table_name'], c['column_name'], c['data_type']
    try:
        expr = col if dt != 'jsonb' else f'{col}::text'
        cur.execute(
            f"SELECT count(*) AS n FROM {t} WHERE {expr} ILIKE '%SIG_START%' OR {expr} ILIKE '%SIG_END%'"
        )
        n = cur.fetchone()['n']
        if n:
            hits += 1
            print(f'  HIT: {t}.{col} = {n} rows')
    except Exception as e:
        print(f'  skip {t}.{col}: {e}')
print('TOTAL columns with SIG markers:', hits)

# 2) Kajal signature check (no <br>, no spans)
cur.execute("SELECT content FROM user_signatures WHERE user_id = 3")
sig_rows = cur.fetchall()
print()
print('=== Kajal (user 3) user_signatures ===')
for r in sig_rows:
    c = r['content'] or ''
    print(f'  br tags: {c.count("<br>")} | spans: {c.count("<span")} | SIG markers: {c.count("SIG")}')
cur.execute("SELECT signature FROM users WHERE id = 3")
leg = (cur.fetchone() or {}).get('signature') or ''
print(f'legacy users.signature: br={leg.count("<br>")} spans={leg.count("<span")} SIG={leg.count("SIG")}')

# 3) quick counts of main tables
cur.execute("SELECT count(*) AS n FROM leads_raw WHERE email_draft ILIKE '%SIG_START%' OR email_draft ILIKE '%SIG_END%'")
print()
print('leads_raw.email_draft with SIG markers:', cur.fetchone()['n'])
cur.execute("SELECT count(*) AS n FROM prompts WHERE content ILIKE '%SIG_START%' OR content ILIKE '%SIG_END%'")
print('prompts.content with SIG markers:', cur.fetchone()['n'])
conn.close()
