"""
E2E wiring test against REAL Postgres + Redis.

This is run as its own CI step (NOT under pytest, so it does not inherit the
stubbed-DB conftest). It verifies the application can actually connect to the
infrastructure it depends on and that the health probe reflects the real Redis.
This catches connection-wiring regressions — the historical "max number of
clients reached" (Redis) and "DB pool get failed" (Postgres) incident classes —
in CI without needing a full data seed.

Set E2E_DATABASE_URL / E2E_REDIS_URL (CI service containers) or rely on defaults.
"""
import os
import sys
import time
from pathlib import Path

# Ensure the backend package is importable when run as a standalone script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _env(key: str, default: str) -> str:
    val = os.getenv(key)
    if val:
        return val
    os.environ[key] = default
    return default


# Point the app at the real infrastructure BEFORE importing any app module.
DATABASE_URL = _env("E2E_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/leadstreamai")
REDIS_URL = _env("E2E_REDIS_URL", "redis://localhost:6379/0")
# Force a short connect timeout so a down DB fails fast instead of hanging the
# pool creation (psycopg2 opens minconn connections eagerly).
if "connect_timeout" not in DATABASE_URL:
    DATABASE_URL += "&connect_timeout=5" if "?" in DATABASE_URL else "?connect_timeout=5"
os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["REDIS_URL"] = REDIS_URL
# Minimal settings so the app imports cleanly in CI.
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")
os.environ.setdefault("DEBUG", "true")


def _fail(msg: str):
    print("E2E FAIL:", msg)
    sys.exit(1)


def _wait(label: str, fn, attempts: int = 30, delay: float = 1.0):
    last = None
    for i in range(attempts):
        try:
            fn()
            print(f"OK: {label}")
            return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(delay)
    _fail(f"{label} still failing after {attempts}s: {last}")


def main():
    # 1. Real Redis is reachable. Use a short socket timeout so a missing
    #    service fails fast instead of blocking on the default (unbounded) connect.
    import redis as _redis_mod

    def _redis():
        _redis_mod.Redis.from_url(
            REDIS_URL, socket_connect_timeout=3, socket_timeout=3
        ).ping()

    _wait("Redis reachable", _redis)

    # 2. Real Postgres is reachable through the app's connection pool.
    from app.database import get_db_connection

    def _pg():
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
            cur.close()
        finally:
            conn.close()

    _wait("Postgres reachable via app pool", _pg, attempts=15, delay=1)

    # 3. The app boots and its health probe reflects the REAL redis pool.
    import app.main as m
    from fastapi.testclient import TestClient

    # No `with` — we deliberately skip lifespan (background loops / create_tables)
    # since this test is about infra wiring, not data/migrations.
    c = TestClient(m.app)
    r = c.get("/api/health/redis")
    if r.status_code != 200:
        _fail(f"/api/health/redis returned {r.status_code}: {r.text[:200]}")
    body = r.json()
    if body.get("configured") is not True or body.get("status") != "healthy":
        _fail(f"/api/health/redis not healthy: {body}")
    print("OK: /api/health/redis reflects real Redis ->", body)

    print("E2E PASS: real Postgres + Redis wiring verified")


if __name__ == "__main__":
    main()
