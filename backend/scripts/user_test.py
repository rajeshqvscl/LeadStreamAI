import psycopg2
from app.database import get_db_connection

try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, name FROM users;")
    for r in cur.fetchall():
        print(r)
except Exception as e:
    print("Error:", e)
