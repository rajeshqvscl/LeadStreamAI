#!/usr/bin/env python3
"""
API Contract Verification
=======================
Catches the two most common recurring bugs in this codebase:

1. ROUTE COLLISIONS - two routers both register the same path+method, so
   the wrong handler silently wins (e.g. /api/metrics served Prometheus text
   instead of the engagement report).

2. MISSING ROUTES - a frontend page calls /api/X but no backend route exists,
   producing 404s or silent empty data.

Usage:
    python scripts/verify_api_contract.py
    python scripts/verify_api_contract.py --frontend ../frontend/src

Exit code 0 = OK, 1 = problems found.
"""
import os
import re
import sys
import glob
import argparse

# Ensure the backend package root is importable when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env (stale DATABASE_URL guard) before importing the app
from dotenv import load_dotenv
load_dotenv("app/.env", override=True)
try:
    with open("app/.env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"')
except FileNotFoundError:
    pass

import app.main as m

FRONTEND_ROOT = "../frontend/src"


def normalize(path: str) -> str:
    """Normalize a URL path so literal resource segments match placeholders.

    /api/leads/123/activity   -> /api/leads/*/activity
    /api/leads/{lead_id}      -> /api/leads/*/activity
    /api/leads/${leadId}      -> /api/leads/*/activity
    """
    segs = path.split("/")
    out = []
    for s in segs:
        if not s:
            continue
        # openapi placeholder
        if s.startswith("{") and s.endswith("}"):
            out.append("*")
            continue
        # frontend template literal
        if s.startswith("${") and s.endswith("}"):
            out.append("*")
            continue
        # numeric or uuid-ish -> placeholder
        if re.fullmatch(r"\d+", s) or re.fullmatch(r"[0-9a-fA-F-]{8,}", s):
            out.append("*")
            continue
        out.append(s.lower())
    return "/" + "/".join(out)


def get_openapi_paths():
    spec = m.app.openapi()
    return {p: set(d.keys()) for p, d in spec.get("paths", {}).items()}


def get_collisions():
    """Detect duplicate (path, method) registrations in the mounted app."""
    seen = {}
    collisions = []
    for r in m.app.routes:
        methods = getattr(r, "methods", None)
        path = getattr(r, "path", None)
        if not methods or not path:
            continue
        for meth in methods:
            key = (path, meth)
            if key in seen:
                collisions.append((path, meth, seen[key], getattr(r, "endpoint", None).__module__))
            else:
                ep = getattr(r, "endpoint", None)
                seen[key] = getattr(ep, "__module__", "?") + "." + getattr(ep, "__qualname__", "?")
    return collisions


def extract_frontend_paths(root: str):
    paths = set()
    for ext in ("*.jsx", "*.js"):
        for fp in glob.glob(os.path.join(root, "**", ext), recursive=True):
            src = open(fp, encoding="utf-8", errors="ignore").read()
            for mt in re.findall(r"['\"`](/api/[^'\"`?$\s{}]+)", src):
                paths.add(mt.split("?")[0].rstrip("/"))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default=FRONTEND_ROOT)
    args = ap.parse_args()

    print("=" * 60)
    print("API CONTRACT VERIFICATION")
    print("=" * 60)

    spec = get_openapi_paths()
    norm_spec = {normalize(p): (p, ms) for p, ms in spec.items()}

    # 1. Collision detection
    collisions = get_collisions()
    print(f"\n[1] ROUTE COLLISIONS: {len(collisions)} found")
    if collisions:
        for path, meth, first, second in collisions:
            print(f"    CONFLICT {meth} {path}")
            print(f"        first : {first}")
            print(f"        second: {second}")

    # 2. Frontend path coverage
    fe_paths = extract_frontend_paths(args.frontend)
    print(f"\n[2] FRONTEND API PATHS: {len(fe_paths)} referenced")

    missing = []
    for p in sorted(fe_paths):
        key = normalize(p)
        if key in norm_spec:
            continue
        # Allow prefix match: frontend path is a parent of a parametrized route
        # (e.g. /api/gmail/send-draft is the base of /api/gmail/send-draft/{id})
        if any(k.startswith(key + "/") or k == key for k in norm_spec):
            continue
        missing.append(p)

    print(f"    MISSING (no backend route): {len(missing)}")
    for p in missing:
        print(f"    MISSING: {p}")

    # 3. Verdict
    ok = (not collisions) and (not missing)
    print("\n" + "=" * 60)
    if ok:
        print("RESULT: PASS - no collisions, all frontend paths have routes")
        sys.exit(0)
    else:
        print("RESULT: FAIL - see items above")
        sys.exit(1)


if __name__ == "__main__":
    main()
