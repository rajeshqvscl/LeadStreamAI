#!/usr/bin/env python3
"""
LeadStream — Performance Baseline Harness

Measures the operational numbers the system has no formal baseline for yet:

  1. API latency (p50/p95/p99) against a live backend
  2. Database round-trip latency + row-count snapshot (read-only)
  3. Redis queue depth + drain rate over the measurement window

Usage (run from backend/, against STAGING first — never assume prod):

    # API latency only (public endpoints)
    python scripts/load_baseline.py --base-url https://staging-backend.onrender.com

    # API latency including an authenticated read (staging token)
    python scripts/load_baseline.py --base-url ... --token <session-token>

    # Everything (DB + Redis reachable from this machine)
    DATABASE_URL=... REDIS_URL=... python scripts/load_baseline.py \
        --base-url ... --token ... --duration 60

    # Save machine-readable report
    ... --out /tmp/baseline_20260903.json

Exit code: 0 on success; 1 if a hard failure prevented measurement.
Thresholds are NOT enforced here — they are reviewed against
project-brain/ARCHITECTURE.md §25 by a human after each run.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

import requests


def measure_http_latency(base_url: str, token: str | None, n: int) -> dict:
    """p50/p95/p99 latency for /api/v1/health/startup and (with token) /api/leads/."""
    results: dict[str, list[float]] = {}

    def _hit(path: str, headers: dict) -> None:
        url = base_url.rstrip("/") + path
        latencies = []
        for _ in range(n):
            start = time.perf_counter()
            try:
                r = requests.get(url, headers=headers, timeout=15)
                r.raise_for_status()
            except Exception as e:  # noqa: BLE001 — record the failure
                latencies.append(-1)
                print(f"  ⚠ {path} request failed: {e}")
                continue
            latencies.append((time.perf_counter() - start) * 1000)
        ok = [x for x in latencies if x >= 0]
        results[path] = {"ok": len(ok), "failed": len(latencies) - len(ok)}
        if ok:
            ok.sort()
            results[path].update({
                "p50_ms": round(statistics.median(ok), 1),
                "p95_ms": round(ok[int(len(ok) * 0.95) - 1], 1),
                "p99_ms": round(ok[int(len(ok) * 0.99) - 1], 1),
                "min_ms": round(ok[0], 1),
                "max_ms": round(ok[-1], 1),
            })

    print(f"\n1) HTTP latency — {n} requests per endpoint to {base_url}")
    _hit("/api/v1/health/startup", {})
    if token:
        _hit("/api/leads/?page=1&per_page=5", {"Authorization": f"Bearer {token}"})
    return results


def measure_db(db_url: str) -> dict:
    """Read-only DB round-trip + table snapshot."""
    print("\n2) Database (read-only)")
    try:
        import psycopg2
    except ImportError:
        print("  ⚠ psycopg2 not installed — skipping DB measurement")
        return {"skipped": True}

    out: dict = {"skipped": False}
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        # Round-trip latency (10 samples)
        lat = []
        for _ in range(10):
            t = time.perf_counter()
            cur.execute("SELECT 1")
            cur.fetchone()
            lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        out["roundtrip_ms"] = {
            "p50": round(statistics.median(lat), 2),
            "p95": round(lat[int(len(lat) * 0.95) - 1], 2),
        }
        # Table snapshot
        tables = {
            "leads_raw": "SELECT count(*) FROM leads_raw",
            "users": "SELECT count(*) FROM users",
            "activity_log": "SELECT count(*) FROM activity_log",
            "email_idempotency": "SELECT count(*) FROM email_idempotency",
            "email_status_sent": "SELECT count(*) FROM leads_raw WHERE email_status = 'SENT'",
            "followup_active": "SELECT count(*) FROM leads_raw WHERE followup_status = 'ACTIVE' AND COALESCE(is_responded, FALSE) = FALSE",
        }
        for label, sql in tables.items():
            try:
                cur.execute(sql)
                out[label] = cur.fetchone()[0]
            except Exception as e:  # noqa: BLE001
                out[label] = f"error: {e}"
        cur.close()
        conn.close()
        for k in ("roundtrip_ms", *tables.keys()):
            print(f"  {k}: {out.get(k)}")
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ DB measurement failed: {e}")
        return {"skipped": True, "error": str(e)}


def measure_redis(redis_url: str, duration: float) -> dict:
    """Queue depth at t0 and drain/production rate over `duration` seconds."""
    print("\n3) Redis queues")
    try:
        import redis as redis_lib
    except ImportError:
        print("  ⚠ redis not installed — skipping Redis measurement")
        return {"skipped": True}

    r = redis_lib.Redis.from_url(redis_url, socket_connect_timeout=10, socket_timeout=10)
    queues = ["emails_high", "emails_normal", "emails_low", "emails_scheduled", "emails_dlq"]
    try:
        depth0 = {q: r.llen(q) for q in queues}
        # RQ failed-job registry depth
        for q in queues:
            try:
                depth0[f"{q}:failed_registry"] = r.zcard(f"rq:queue:{q}:failed")
            except Exception:  # noqa: BLE001
                pass
        print(f"  depth@t0: {json.dumps(depth0)}")
        time.sleep(max(duration, 5))
        depth1 = {q: r.llen(q) for q in queues}
        delta = {
            q: (depth0[q] - depth1[q]) for q in queues
        }
        rate = {
            q: round((depth0[q] - depth1[q]) / max(duration, 5), 2)
            for q in queues
        }
        print(f"  depth@t1: {json.dumps(depth1)}")
        print(f"  drain/sec: {json.dumps(rate)} (negative = jobs added)")
        return {
            "depth_t0": depth0,
            "depth_t1": depth1,
            "delta": delta,
            "drain_per_sec": rate,
        }
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ Redis measurement failed: {e}")
        return {"skipped": True, "error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=os.getenv("BASE_URL", ""), help="Backend base URL")
    ap.add_argument("--token", default=os.getenv("BASELINE_TOKEN", ""), help="Session token for authenticated reads")
    ap.add_argument("--requests", type=int, default=20, help="HTTP samples per endpoint")
    ap.add_argument("--duration", type=float, default=15.0, help="Redis drain observation window (s)")
    ap.add_argument("--out", default="", help="Write JSON report to this path")
    args = ap.parse_args()

    if not args.base_url:
        print("ERROR: --base-url required (or BASE_URL env)")
        return 1

    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "config": vars(args),
    }

    report["http"] = measure_http_latency(args.base_url, args.token or None, args.requests)

    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        report["db"] = measure_db(db_url)
    else:
        print("\n2) DB measurement skipped (DATABASE_URL not set)")

    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        report["redis"] = measure_redis(redis_url, args.duration)
    else:
        print("\n3) Redis measurement skipped (REDIS_URL not set)")

    print("\n" + "=" * 60)
    print("Baseline report:")
    print(json.dumps(report, indent=2, default=str))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nSaved to {args.out}")

    print("\nReview against project-brain/ARCHITECTURE.md §25 (NFRs). "
          "No thresholds enforced — this is the measurement, not the gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
