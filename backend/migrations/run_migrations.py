#!/usr/bin/env python3
"""
Database migration runner for LeadStreamAI.
Run with: python -m migrations.run_migrations
"""

import os
import sys
import glob
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db_connection


def run_migrations():
    """Run all SQL migration files in order."""
    migrations_dir = Path(__file__).parent
    migration_files = sorted(glob.glob(str(migrations_dir / "*.sql")))
    
    if not migration_files:
        print("No migration files found")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create migrations tracking table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(50) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    
    # Get already applied migrations
    cur.execute("SELECT version FROM schema_migrations")
    applied = {row[0] for row in cur.fetchall()}
    
    for migration_file in migration_files:
        version = Path(migration_file).stem
        
        if version in applied:
            print(f"⏭  Skipping {version} (already applied)")
            continue
        
        print(f"🔄 Applying {version}...")
        try:
            with open(migration_file, 'r') as f:
                sql = f.read()
            
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for stmt in statements:
                if stmt:
                    cur.execute(stmt)
            
            # Record migration
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()
            print(f"✅ Applied {version}")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Failed to apply {version}: {e}")
            raise
    
    cur.close()
    conn.close()
    print("🎉 All migrations complete")


if __name__ == "__main__":
    run_migrations()