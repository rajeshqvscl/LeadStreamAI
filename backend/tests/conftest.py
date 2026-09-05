"""
Pytest configuration and shared fixtures.
"""
import pytest
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ---------------------------------------------------------------------------
# Test environment variables
#
# CI (GitHub Actions) provides a real PostgreSQL/Redis via service containers
# and sets DATABASE_URL/REDIS_URL explicitly — keep those. Locally we force
# sandbox values so tests never reach the credentials in backend/app/.env
# (several app modules call load_dotenv(override=True) on that file).
# ---------------------------------------------------------------------------
os.environ["DEBUG"] = "true"

if os.environ.get("CI") == "true" and os.environ.get("DATABASE_URL"):
    _TEST_DATABASE_URL = os.environ["DATABASE_URL"]
else:
    _TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/test"
    os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

if os.environ.get("CI") == "true" and os.environ.get("REDIS_URL"):
    _TEST_REDIS_URL = os.environ["REDIS_URL"]
else:
    _TEST_REDIS_URL = "redis://localhost:6379/15"
    os.environ["REDIS_URL"] = _TEST_REDIS_URL

os.environ["ADMIN_PASSWORD"] = "testpassword123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["GOOGLE_CLIENT_ID"] = "test"
os.environ["GOOGLE_CLIENT_SECRET"] = "test"
# Encryption key so OAuth token roundtrip tests exercise real encryption
os.environ["TOKEN_ENCRYPTION_KEY"] = "pytest-token-encryption-key"


def db_reachable() -> bool:
    """True if a real PostgreSQL is listening on the TEST database URL.

    Checks ``_TEST_DATABASE_URL`` — NOT the ambient ``DATABASE_URL`` env var.
    App modules call ``load_dotenv(override=True)`` at import time, which
    flips ``DATABASE_URL`` to the URL in backend/app/.env (the REAL production
    database). Reading the ambient var here made local test runs see the
    production DB as "reachable" and seed pytest rows into it. The sandbox
    URL never changes, so the stub-vs-real decision is stable and can never
    point at production.

    Raw TCP check so it is not fooled by app-level DB stubs. Test modules and
    fixtures can import this: ``from tests.conftest import db_reachable``
    (tests/ is importable when pytest runs from backend/).
    """
    from urllib.parse import urlparse
    import socket

    url = _TEST_DATABASE_URL
    if not url:
        return False
    p = urlparse(url.replace("postgresql://", "http://"))
    host = p.hostname or "localhost"
    port = p.port or 5432
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _protect_test_env():
    """Keep test DB/Redis pointed at the sandbox before and after every test,
    regardless of any ``load_dotenv(override=True)`` in app code."""
    os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
    os.environ["REDIS_URL"] = _TEST_REDIS_URL
    yield
    os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
    os.environ["REDIS_URL"] = _TEST_REDIS_URL


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_lead_data():
    """Sample lead data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "company_name": "Example Corp",
        "designation": "CTO",
        "persona": "EXECUTIVE",
        "sector": "Technology",
        "phone": "+1-555-0100",
        "city": "San Francisco",
        "country": "USA",
    }


@pytest.fixture
def sample_investor_lead():
    """Sample investor lead data."""
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@sequoiacap.com",
        "company_name": "Sequoia Capital",
        "designation": "General Partner",
        "persona": "INVESTOR",
        "sector": "Venture Capital",
    }


@pytest.fixture
def mock_db_connection(mocker):
    """Mock database connection for unit tests."""
    mock_conn = mocker.MagicMock()
    mock_cur = mocker.MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.cursor.return_value.__exit__.return_value = None
    return mock_conn, mock_cur


# ---------------------------------------------------------------------------
# Integration-test support: fake DB + authenticated TestClient
# ---------------------------------------------------------------------------
class FakeRow(dict):
    """Dict that also tolerates integer indexing (DictCursor semantics)."""

    def __getitem__(self, k):
        if isinstance(k, int):
            return 0
        return super().__getitem__(k) if k in self else 0

    def get(self, k, d=None):
        return super().get(k, 0)


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        return None

    def fetchone(self):
        return FakeRow()

    def fetchall(self):
        return []

    def close(self):
        return None

    rowcount = 0


class FakeConn:
    def cursor(self, *a, **k):
        return FakeCursor()

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


@pytest.fixture(scope="session")
def client():
    """Authenticated TestClient.

    TWO MODES, decided once per session by whether a real PostgreSQL is up:

    * **Real-DB mode** (CI service container): no stubbing at all. API modules
      hit the real DB and ``_verify_session`` validates real session rows, so
      forged tokens 401 and ownership checks run against seeded data. Use the
      ``security_seed`` fixtures (tests/unit/conftest.py) to seed users/leads.
    * **Stub mode** (no local DB): installs a FakeConn for every
      ``get_db_connection`` binding (patched BEFORE ``app.main`` is imported so
      ``from app.database import get_db_connection`` in API modules picks it
      up) and bypasses session verification (any token -> user "1"). Endpoint
      ownership shape still holds: a FakeRow has user_id 0, so cross-user
      requests 404.

    Session-scoped because FastAPI lifespan startup is expensive.
    """
    import app.database as dbmod

    real_db = db_reachable()

    if real_db:
        # ---- Real-DB mode: no patching ----
        import app.main as mainmod
        from fastapi.testclient import TestClient

        with TestClient(mainmod.app) as c:
            yield c
        return

    # ---- Stub mode ----
    _orig_db = dbmod.get_db_connection

    def _fake_get_db(*a, **k):
        return FakeConn()

    dbmod.get_db_connection = _fake_get_db  # before app.main import

    import app.main as mainmod
    import app.core.rate_limiter as rlmod

    _orig_verify = mainmod._verify_session
    _orig_check = rlmod.SlidingWindowRateLimiter.check_limit

    def _fake_verify(token):
        return "1"

    async def _fake_check_limit(self, key, limit=None, window=None):
        return True, {
            "allowed": True,
            "current": 0,
            "limit": limit or 100,
            "reset_at": 0,
            "retry_after": 0,
        }

    try:
        mainmod._verify_session = _fake_verify
        rlmod.SlidingWindowRateLimiter.check_limit = _fake_check_limit

        from fastapi.testclient import TestClient

        with TestClient(mainmod.app) as c:
            yield c
    finally:
        mainmod._verify_session = _orig_verify
        dbmod.get_db_connection = _orig_db
        rlmod.SlidingWindowRateLimiter.check_limit = _orig_check


@pytest.fixture
def auth_headers():
    # X-User-Id is required because AuthMiddleware caches request.headers before
    # it can override the header; handlers that read X-User-Id via Header() rely
    # on the client (frontend) supplying it. The middleware re-overrides it with
    # the verified session id anyway, so "1" is safe for tests.
    return {"Authorization": "Bearer test-token", "X-User-Id": "1"}
