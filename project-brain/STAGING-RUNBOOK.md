# LeadStream — Staging Environment Runbook

> **Status: 🟡 Not yet live.** `backend/scripts/setup_staging.sh` exists but no staging
> services have been deployed. Completing this runbook closes Gate 3 gap #2.
> Owner: backend admin (needs Neon + Render access). Do **not** use production Gmail
> credentials anywhere in staging.

## Target topology

```text
DEV ──PR──▶ CI (tests) ──deploy──▶ STAGING (Render) ──promote──▶ PRODUCTION (Render)

Staging:  separate Neon DB | separate Redis | test Gmail | staging AI keys
```

## Prerequisites

1. **Neon** account → create a second project: `leadstream-staging` (scratch DB, e.g. 0.5 GB — staging data is throwaway).
2. **Render** account → same org as production (reuse the blueprint/service pattern).
3. **Test Gmail account** (e.g. `test-qvscl@...`) + Google OAuth client configured for the staging redirect URI.
4. Local access to this repo + `openssl` (Windows Git Bash has it) + PostgreSQL client tools for verification.

## Step 1 — Collect staging URLs

```bash
# From Neon console:  DATABASE_URL_STAGING  (postgresql://user:pass@host/leadstream_staging)
# From Render:        REDIS_URL_STAGING     (or use the same Render Redis with namespace /1)
export DATABASE_URL_STAGING="postgresql://..."      # ← never paste into the repo
export REDIS_URL_STAGING="redis://..."              # optional
```

## Step 2 — Generate the staging env file

```bash
cd backend
./scripts/setup_staging.sh          # writes backend/.env.staging
```

This creates `.env.staging` with: staging DB URL, random staging admin password,
random `TOKEN_ENCRYPTION_KEY` (independent from prod — OAuth tokens encrypted with
the staging key only decrypt in staging), staging Gmail client IDs, staging URLs,
and a **staging admin user** seeded into the staging DB.

> `setup_staging.sh` defaults `GOOGLE_CLIENT_ID/SECRET` and URLs to placeholder
> values — replace them with the real staging OAuth client + staging Render URLs
> before deploying (edit `.env.staging`).

## Step 3 — Create Render staging services

Create **three** services (mirror production):

| Service | Type | Key env (from `.env.staging`) |
|---|---|---|
| `leadstream-staging-api` | Web (gunicorn/uvicorn, `main:app`) | `DATABASE_URL`, `REDIS_URL`, `TOKEN_ENCRYPTION_KEY`, `GOOGLE_*` (staging OAuth), `CORS_ALLOWED_ORIGINS=https://staging-frontend.onrender.com`, `BACKEND_URL`, `FRONTEND_URL`, `SCHEDULER_*` |
| `leadstream-staging-worker` | Background worker (`python worker.py`) | same DB/Redis keys + Gmail/AI keys |
| `leadstream-staging-frontend` | Static site (`npm run build`, `VITE_API_BASE_URL=https://staging-api...`) | — |

Easiest: clone the production service → rename → point env at staging values.
Do **not** copy production env vars wholesale — replace DB/Redis/OAuth/encryption key.

## Step 4 — Deploy & verify

```bash
# Deploy (push to a staging branch or use Render deploy hooks).
# Then, once the API is up:
cd backend

# 4.1 Health + dispatcher
curl -s https://staging-api.onrender.com/api/health/ready | python -m json.tool
#    → expect: database ✅ redis ✅ email_dispatcher healthy

# 4.2 Smoke + contract
python scripts/smoke_test.py
DATABASE_URL="$DATABASE_URL_STAGING" python scripts/verify_api_contract.py --frontend ../frontend/src

# 4.3 Security + integration suites against staging
DATABASE_URL="$DATABASE_URL_STAGING" python -m pytest tests/unit/test_cross_user_security.py tests/unit/test_endpoint_security.py -q
DATABASE_URL="$DATABASE_URL_STAGING" python -m pytest tests/integration -q

# 4.4 Connect the TEST Gmail account via the staging UI (staging OAuth client)
#     → confirm one send + one reply round-trip in staging, NOT production.
```

## Step 5 — Performance baseline (first numbers)

```bash
DATABASE_URL="$DATABASE_URL_STAGING" REDIS_URL="$REDIS_URL_STAGING" \
  python scripts/load_baseline.py \
  --base-url https://staging-api.onrender.com \
  --token "$(staging session token)" \
  --duration 30 --out /tmp/baseline_staging.json
```

Record the output in `project-brain/ARCHITECTURE.md` §25 (NFRs) once measured.

## Step 6 — CI promotion (optional but recommended)

Add a CI job to `.github/workflows/ci.yml` that deploys to staging **after** the
security + integration gates pass (Render deploy hook per service), so the same
release candidate that passes tests is what staging runs. Production remains
externally promoted as today.

## Golden rule

- **Production Gmail accounts / production OAuth / production DB must never be used in staging.**
- If a staging run needs realistic data, restore an anonymized dump into the staging DB
  with `scripts/restore.sh` (see `project-brain/DR.md`) — never point staging at prod DB.
- Staging sends go out from the **test Gmail account only**.
