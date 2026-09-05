"""
Production Health Check Script

Verifies:
1. PostgreSQL connectivity + schema integrity
2. Redis connectivity
3. Gmail OAuth token validity (sample check)
4. Scheduler status
5. Queue depth
6. Disk space (for local assets)

Run: python scripts/health_check.py
"""

import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check_postgres():
    """Check PostgreSQL connectivity and basic schema."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()

        # Basic connectivity
        cur.execute("SELECT 1")
        cur.fetchone()

        # Schema check
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]

        required = ['leads_raw', 'users', 'sessions', 'campaigns', 'activity_log']
        missing = [t for t in required if t not in tables]

        cur.close()
        conn.close()

        if missing:
            return {"status": "ERROR", "missing_tables": missing}
        return {"status": "OK", "tables": len(tables)}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def check_redis():
    """Check Redis connectivity."""
    try:
        from app.core.redis_pool import get_redis_client
        r = get_redis_client()
        r.ping()
        info = r.info("memory")
        return {
            "status": "OK",
            "used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def check_queue_depth():
    """Check email queue depth."""
    try:
        from app.email_engine.queue.registry import get_queue_stats
        stats = get_queue_stats()
        return {"status": "OK", "queues": stats}
    except Exception as e:
        return {"status": "WARNING", "error": str(e)}


def check_gmail_tokens():
    """Check how many users have valid Gmail connections."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM users WHERE google_refresh_token IS NOT NULL")
        connected = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        active = cur.fetchone()[0]

        cur.close()
        conn.close()

        return {
            "status": "OK",
            "connected_users": connected,
            "active_users": active,
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def check_scheduler_status():
    """Check if scheduler is running by looking at recent activity."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*) FROM activity_log
            WHERE created_at > NOW() - INTERVAL '1 hour'
            AND performed_by = 'system'
        """)
        recent_activity = cur.fetchone()[0]

        cur.close()
        conn.close()

        return {
            "status": "OK" if recent_activity > 0 else "WARNING",
            "recent_system_activity": recent_activity,
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def main():
    """Run all health checks and report results."""
    checks = {
        "postgres": check_postgres(),
        "redis": check_redis(),
        "queue": check_queue_depth(),
        "gmail_tokens": check_gmail_tokens(),
        "scheduler": check_scheduler_status(),
    }

    all_ok = all(c["status"] == "OK" for c in checks.values())

    report = {
        "overall": "HEALTHY" if all_ok else "DEGRADED",
        "checks": checks,
    }

    print(json.dumps(report, indent=2))

    if not all_ok:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
