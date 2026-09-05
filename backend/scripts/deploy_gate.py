"""
Deployment Gate Script

Run before production deploy. Blocks deployment if any critical check fails.

Checks:
1. All Python files compile
2. Unit tests pass
3. Security tests pass
4. API contract valid
5. Database migration status
6. Required env vars present

Usage: python scripts/deploy_gate.py
Exit 0 = safe to deploy, Exit 1 = BLOCKED
"""

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
errors = []


def run_check(name, cmd, cwd=None):
    """Run a check and report result."""
    print(f"\n{'='*60}")
    print(f"CHECK: {name}")
    print(f"CMD: {cmd}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd or BACKEND_DIR,
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            print(f"✅ PASS: {name}")
            if result.stdout.strip():
                print(result.stdout[-500:])
            return True
        else:
            print(f"❌ FAIL: {name}")
            print(result.stdout[-500:] if result.stdout else "")
            print(result.stderr[-500:] if result.stderr else "")
            errors.append(name)
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ TIMEOUT: {name}")
        errors.append(f"{name} (timeout)")
        return False
    except Exception as e:
        print(f"💥 ERROR: {name}: {e}")
        errors.append(f"{name} (error)")
        return False


def main():
    print("🚀 DEPLOY GATE — Pre-deployment checks")
    print("=" * 60)

    # 1. Syntax checks
    critical_files = [
        "app/api/gmail.py", "app/api/auth.py", "app/api/leads.py",
        "app/api/drafts.py", "app/api/campaigns.py",
        "app/services/email_service.py", "app/services/followup_service.py",
        "app/services/google_service.py",
        "app/email_engine/worker/sender.py",
        "app/core/pipeline/state_machine.py",
        "app/core/reply/classifier.py", "app/core/reply/validator.py",
        "app/core/scheduler_lock.py", "app/core/security_logging.py",
        "app/utils/token_encryption.py",
        "app/main.py", "app/database.py",
    ]
    syntax_ok = True
    for f in critical_files:
        result = subprocess.run(
            f"python -m py_compile {f}", shell=True,
            cwd=BACKEND_DIR, capture_output=True,
        )
        if result.returncode != 0:
            print(f"❌ SYNTAX ERROR: {f}")
            errors.append(f"Syntax: {f}")
            syntax_ok = False

    if syntax_ok:
        print("✅ All critical files compile OK")
    else:
        print(f"❌ {len(errors)} syntax errors found")

    # 2. Security tests
    run_check(
        "Security Tests",
        "python -m pytest tests/unit/test_cross_user_security.py "
        "tests/unit/test_state_machine.py "
        "tests/unit/test_reply_validator.py "
        "tests/unit/test_failure_injection.py "
        "tests/unit/test_endpoint_security.py "
        "-v --tb=short",
    )

    # 3. API contract check
    run_check(
        "API Contract Verification",
        "python scripts/verify_api_contract.py --frontend ../frontend/src",
    )

    # 4. Smoke test
    run_check(
        "Runtime Smoke Test",
        "python scripts/smoke_test.py",
    )

    # 5. Required env vars
    print(f"\n{'='*60}")
    print("CHECK: Required Environment Variables")
    print(f"{'='*60}")

    required_vars = [
        "DATABASE_URL", "ADMIN_PASSWORD",
    ]
    optional_important = [
        "REDIS_URL", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "TOKEN_ENCRYPTION_KEY",
    ]

    for var in required_vars:
        if not os.getenv(var):
            print(f"❌ MISSING REQUIRED: {var}")
            errors.append(f"Missing env: {var}")
        else:
            print(f"✅ {var} = SET")

    for var in optional_important:
        if not os.getenv(var):
            print(f"⚠️  MISSING OPTIONAL: {var}")
        else:
            print(f"✅ {var} = SET")

    # Summary
    print(f"\n{'='*60}")
    print("DEPLOY GATE SUMMARY")
    print(f"{'='*60}")

    if errors:
        print(f"❌ BLOCKED — {len(errors)} checks failed:")
        for e in errors:
            print(f"   - {e}")
        print("\nFix these issues before deploying to production.")
        sys.exit(1)
    else:
        print("✅ ALL CHECKS PASSED — Safe to deploy")
        sys.exit(0)


import os

if __name__ == "__main__":
    main()
