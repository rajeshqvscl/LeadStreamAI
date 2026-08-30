"""
Pytest configuration and shared fixtures.
"""
import pytest
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set test environment variables
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["ADMIN_PASSWORD"] = "testpassword123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["GOOGLE_CLIENT_ID"] = "test"
os.environ["GOOGLE_CLIENT_SECRET"] = "test"


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


@pytest.fixture
def fake_db(monkeypatch):
    """Patch get_db_connection everywhere it is imported."""
    import app.database as dbmod

    monkeypatch.setattr(dbmod, "get_db_connection", lambda *a, **k: FakeConn())
    # also patch the alias used inside some modules
    try:
        import app.api.metrics as mm

        monkeypatch.setattr(mm, "get_db_connection", lambda *a, **k: FakeConn())
    except Exception:
        pass
    return FakeConn


@pytest.fixture
def client(fake_db, monkeypatch):
    """Authenticated TestClient with a stubbed DB and auth bypass."""
    import app.main as mainmod
    import app.core.rate_limiter as rlmod

    # Bypass session verification: any bearer token -> user "1"
    # NOTE: _verify_session is a SYNC function (called via asyncio.to_thread),
    # so the fake must also be sync.
    def _fake_verify(token):
        return "1"

    monkeypatch.setattr(mainmod, "_verify_session", _fake_verify)

    # Stub the Redis-backed rate limiter (no Redis in test env). Patch the class
    # method so the already-instantiated middleware limiter picks it up.
    async def _fake_check_limit(self, key, limit=None, window=None):
        return True, {
            "allowed": True,
            "current": 0,
            "limit": limit or 100,
            "reset_at": 0,
            "retry_after": 0,
        }

    monkeypatch.setattr(rlmod.SlidingWindowRateLimiter, "check_limit", _fake_check_limit)

    from fastapi.testclient import TestClient

    with TestClient(mainmod.app) as c:
        yield c


@pytest.fixture
def auth_headers():
    # X-User-Id is required because AuthMiddleware caches request.headers before
    # it can override the header; handlers that read X-User-Id via Header() rely
    # on the client (frontend) supplying it. The middleware re-overrides it with
    # the verified session id anyway, so "1" is safe for tests.
    return {"Authorization": "Bearer test-token", "X-User-Id": "1"}
