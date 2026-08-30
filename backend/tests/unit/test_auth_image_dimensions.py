"""Tests for auth.py endpoints — verifies image_width/image_height returned.

Uses the same FakeConn pattern from conftest.py but patches at app.database level
since auth.py imports get_db_connection directly from app.database.
"""
import pytest
import os, sys
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")


class FakeRow(dict):
    def __getitem__(self, k):
        if isinstance(k, int):
            return 0
        return super().__getitem__(k) if k in self else 0
    def get(self, k, d=None):
        return super().get(k, 0)


class FakeCursor:
    def __init__(self, user=None):
        self._user = user
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, *a, **k): pass
    def fetchone(self): return self._user
    def fetchall(self): return []
    def close(self): pass
    rowcount = 0


class FakeConn:
    def __init__(self, user=None):
        self._user = user
    def cursor(self, *a, **k): return FakeCursor(self._user)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


def _user_dict(**overrides):
    base = {
        "id": 1, "username": "testuser", "email": "test@example.com",
        "full_name": "Test User", "password_hash": "$2b$12$fakehash",
        "role": "USER", "team": "CLIENT", "is_active": True, "is_approved": True,
        "signature": None, "signature_mode": "custom",
        "image_width": "300px", "image_height": "250px",
    }
    base.update(overrides)
    return FakeRow(base)


@pytest.fixture
def fake_user():
    return _user_dict()


@pytest.fixture
def patched_auth(fake_user, monkeypatch):
    """Patch get_db_connection at app.database level so all modules see it."""
    import app.database as dbmod
    import app.api.auth as auth_mod

    monkeypatch.setattr(dbmod, "get_db_connection", lambda *a, **k: FakeConn(fake_user))
    # auth.py also imports get_db_connection directly — rebind the local ref
    monkeypatch.setattr(auth_mod, "get_db_connection", lambda *a, **k: FakeConn(fake_user))
    return auth_mod


@pytest.fixture
def auth_client(patched_auth, monkeypatch):
    """TestClient with bcrypt patched (no real hash verification)."""
    import app.api.auth as auth_mod
    monkeypatch.setattr(auth_mod.bcrypt, "checkpw", lambda *a: True)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(auth_mod.router, prefix="/api/auth")
    return TestClient(app, raise_server_exceptions=False)


class TestLoginReturnsImageDimensions:

    def test_login_returns_image_width(self, auth_client):
        resp = auth_client.post("/api/auth/login", json={
            "username": "testuser", "password": "pw"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "user" in data
        assert "image_width" in data["user"], "image_width missing"
        assert "image_height" in data["user"], "image_height missing"

    def test_login_image_width_default_when_none(self, monkeypatch):
        user = _user_dict(image_width=None, image_height=None)
        import app.database as dbmod
        monkeypatch.setattr(dbmod, "get_db_connection", lambda *a, **k: FakeConn(user))

        import app.api.auth as auth_mod
        monkeypatch.setattr(auth_mod, "get_db_connection", lambda *a, **k: FakeConn(user))
        monkeypatch.setattr(auth_mod.bcrypt, "checkpw", lambda *a: True)

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(auth_mod.router, prefix="/api/auth")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/auth/login", json={
            "username": "testuser", "password": "pw"
        })
        assert resp.status_code == 200
        assert resp.json()["user"]["image_width"] == "400px"
        assert resp.json()["user"]["image_height"] == "auto"

    def test_login_returns_actual_values(self, monkeypatch):
        user = _user_dict(image_width="200px", image_height="150px")
        import app.database as dbmod
        monkeypatch.setattr(dbmod, "get_db_connection", lambda *a, **k: FakeConn(user))

        import app.api.auth as auth_mod
        monkeypatch.setattr(auth_mod, "get_db_connection", lambda *a, **k: FakeConn(user))
        monkeypatch.setattr(auth_mod.bcrypt, "checkpw", lambda *a: True)

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(auth_mod.router, prefix="/api/auth")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/auth/login", json={
            "username": "testuser", "password": "pw"
        })
        assert resp.status_code == 200
        assert resp.json()["user"]["image_width"] == "200px"
        assert resp.json()["user"]["image_height"] == "150px"


class TestRefreshReturnsImageDimensions:
    """Refresh reads user_id from X-User-Id header, queries DB directly."""

    def test_refresh_returns_image_width(self, patched_auth, monkeypatch):
        import app.api.auth as auth_mod
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(auth_mod.router, prefix="/api/auth")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/auth/refresh", headers={"X-User-Id": "1"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "user" in data
        assert "image_width" in data["user"], "image_width missing"
        assert "image_height" in data["user"], "image_height missing"

    def test_refresh_passes_through_db_values(self, monkeypatch):
        user = _user_dict(image_width="500px", image_height="300px")
        import app.database as dbmod
        monkeypatch.setattr(dbmod, "get_db_connection", lambda *a, **k: FakeConn(user))

        import app.api.auth as auth_mod
        monkeypatch.setattr(auth_mod, "get_db_connection", lambda *a, **k: FakeConn(user))

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(auth_mod.router, prefix="/api/auth")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/auth/refresh", headers={"X-User-Id": "1"})
        assert resp.status_code == 200
        assert resp.json()["user"]["image_width"] == "500px"
        assert resp.json()["user"]["image_height"] == "300px"
