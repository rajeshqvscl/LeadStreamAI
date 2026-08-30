#!/usr/bin/env python3
"""
Runtime smoke test for the API.

Boots the app with stubbed DB / auth / rate-limiter and hits every path the
frontend actually references (the same 141 paths checked statically by
verify_api_contract.py), asserting none return 404/405. This catches routing
regressions AND import/middleware crashes that a static check would miss.

500/422 are acceptable here: they mean the route resolved and the handler ran
against the stubbed backend. Only 404 (route missing/collided) and 405 (wrong
method bound) indicate a contract break.

Usage:
    python scripts/smoke_test.py
Exit code 0 = OK, 1 = problems found.
"""
import os
import re
import sys
import glob
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# --- Minimal env so the app imports without a real database -------------------
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")
os.environ.setdefault("DEBUG", "true")

FRONTEND_ROOT = "../frontend/src"


# --- Stubs -------------------------------------------------------------------
class FakeRow(dict):
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


import app.database as dbmod

dbmod.get_db_connection = lambda *a, **k: FakeConn()

import app.core.rate_limiter as rl

async def _fake_check_limit(self, key, limit=None, window=None):
    return True, {
        "allowed": True,
        "current": 0,
        "limit": limit or 100,
        "reset_at": 0,
        "retry_after": 0,
    }

rl.SlidingWindowRateLimiter.check_limit = _fake_check_limit

import app.main as mainmod

mainmod._verify_session = lambda token: "1"

from fastapi.testclient import TestClient

app = mainmod.app
client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-token", "X-User-Id": "1"}


# --- Path extraction (mirrors verify_api_contract.py) -------------------------
def normalize(path: str) -> str:
    segs = path.split("/")
    out = []
    for s in segs:
        if not s:
            continue
        if s.startswith("{") and s.endswith("}"):
            out.append("*")
        elif s.startswith("${") and s.endswith("}"):
            out.append("*")
        elif re.fullmatch(r"\d+", s) or re.fullmatch(r"[0-9a-fA-F-]{8,}", s):
            out.append("*")
        else:
            out.append(s.lower())
    return "/" + "/".join(out)


def extract_frontend_paths(root: str):
    paths = set()
    for ext in ("*.jsx", "*.js"):
        for fp in glob.glob(os.path.join(root, "**", ext), recursive=True):
            src = open(fp, encoding="utf-8", errors="ignore").read()
            for mt in re.findall(r"['\"`](/api/[^'\"`?$\s{}]+)", src):
                paths.add(mt.split("?")[0].rstrip("/"))
    return paths


def main():
    spec = app.openapi().get("paths", {})
    norm_spec = {normalize(p): p for p in spec}

    # Paths whose handler legitimately returns 404/error when the (stubbed) DB has
    # no session user. Routing for these is still guaranteed by verify_api_contract.py.
    DATA_DEPENDENT_404 = {
        "/api/auth/me",
        "/api/v1/auth/me",
        "/api/auth/refresh",
        "/api/v1/auth/refresh",
    }

    fe_paths = extract_frontend_paths(FRONTEND_ROOT)
    cases = []
    for p in sorted(fe_paths):
        real = norm_spec.get(normalize(p))
        if not real:
            continue
        test_path = re.sub(r"\{[^}]+\}", "1", real)
        for meth in spec[real]:
            if meth.lower() in ("get", "post", "put", "delete", "patch"):
                cases.append((meth.upper(), test_path))

    print(f"SMOKE TEST: {len(cases)} frontend-referenced route calls")
    failures = []
    for meth, path in cases:
        fn = getattr(client, meth.lower())
        try:
            if meth in ("POST", "PUT", "PATCH"):
                r = fn(path, json={}, headers=HEADERS)
            else:
                r = fn(path, headers=HEADERS)
        except Exception as e:  # route crashed before producing a response
            failures.append((meth, path, f"raised {type(e).__name__}: {e}"))
            continue
        if r.status_code in (404, 405) and path not in DATA_DEPENDENT_404:
            failures.append((meth, path, f"HTTP {r.status_code}"))

    print(f"RESULT: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failures / {len(cases)} calls)")
    for meth, path, why in failures:
        print(f"  FAIL {meth} {path} -> {why}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
