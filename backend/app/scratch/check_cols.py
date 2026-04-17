from app.database import get_db_connection

def check_columns():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'leads_raw';")
    cols = [r[0] for r in cur.fetchall()]
    print(f"Columns in leads_raw: {cols}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_columns()
