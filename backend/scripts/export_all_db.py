import psycopg2
import csv
import json
import os
from app.database import get_db_connection

def export_table_to_csv(table_name, filename):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        
        if not rows:
            print(f"Table {table_name} is empty.")
            return

        # Get column names
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
        
        print(f"Successfully exported {table_name} to {filename}")
    except Exception as e:
        print(f"Error exporting {table_name}: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    export_dir = "full_db_exports"
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
        
    tables = [
        "leads_raw", "leads", "email_drafts", "campaigns", 
        "family_offices", "companies", "company_registry", "users",
        "search_history", "activity_log"
    ]
    for table in tables:
        export_table_to_csv(table, f"{export_dir}/{table}_full_export.csv")

