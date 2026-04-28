from app.database import get_db_connection
import psycopg2.extras

try:
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, username, credits_used, credits_limit FROM users;")
    rows = cur.fetchall()
    for row in rows:
        print(f"ID: {row['id']}, User: {row['username']}, Used: {row['credits_used']}, Limit: {row['credits_limit']}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
