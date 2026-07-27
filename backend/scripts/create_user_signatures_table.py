"""
Migration script to create the user_signatures table for multiple signatures.
Run with: python scripts/create_user_signatures_table.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_connection

def migrate():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_signatures (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL DEFAULT 'My Signature',
                content TEXT NOT NULL,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        # Create index for fast lookup by user
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_signatures_user_id ON user_signatures(user_id);
        """)
        # Migrate existing users.signature into the new table as a default named entry
        cur.execute("""
            INSERT INTO user_signatures (user_id, name, content, is_default)
            SELECT id, 'My Signature', signature, TRUE
            FROM users
            WHERE signature IS NOT NULL AND signature != ''
            AND NOT EXISTS (
                SELECT 1 FROM user_signatures WHERE user_id = users.id
            );
        """)
        conn.commit()
        print("✅ user_signatures table created and existing signatures migrated successfully!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
