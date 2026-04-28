from app.database import get_db_connection

try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET credits_limit = 2500;")
    conn.commit()
    print("Updated all users to 2500 credit limit.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
