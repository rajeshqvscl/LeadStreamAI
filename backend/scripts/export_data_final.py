import psycopg2
import csv
import json
import os
from dotenv import load_dotenv

load_dotenv("app/.env")
url = os.getenv("DATABASE_URL")

def export_table(table_name, filename):
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        
        if not rows:
            print(f"Table {table_name} is empty.")
            return

        colnames = [desc[0] for desc in cur.description]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=colnames)
            writer.writeheader()
            for row in rows:
                row_dict = {}
                for i, col in enumerate(colnames):
                    val = row[i]
                    if isinstance(val, (dict, list)):
                        row_dict[col] = json.dumps(val)
                    else:
                        row_dict[col] = val
                writer.writerow(row_dict)
        
        print(f"Exported {len(rows)} rows from {table_name} to {filename}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error exporting {table_name}: {e}")

if __name__ == "__main__":
    out_dir = "historical_exports"
    if not os.path.exists(out_dir): os.makedirs(out_dir)
    
    tables = [
        "leads_raw", "leads", "email_drafts", "family_offices", 
        "companies", "users", "activity_log"
    ]
    for t in tables:
        export_table(t, f"{out_dir}/{t}_old_data.csv")
