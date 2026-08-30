# API Router Rules (MANDATORY for all contributors)

These rules prevent the two most expensive recurring bugs in this project:
**double-prefix 404s** and **route collisions serving the wrong handler**.

---

## 1. How routers are mounted

`app/api/v1/__init__.py` builds two routers:
- `api_v1_router` — prefix `/api/v1` (versioned, preferred)
- `legacy_router` — prefix `/api` (backward-compatible mirror)

Both include the **same set of routers** so every endpoint is reachable at
both `/api/v1/...` and `/api/...`.

---

## 2. Prefix rule (prevents double-prefix 404s)

Look at the **endpoint paths the router defines**, not the file name.

| Router defines endpoints like… | Include WITH prefix | Example |
|---|---|---|
| `/gmail/inbox`, `/dashboard/stats`, `/reminders/due` | **NO prefix** | `legacy_router.include_router(gmail_v1.router)` → `/api/gmail/inbox` |
| `/me`, `/login` (auth.py) | `prefix="/auth"` | `/api/auth/me` |
| `/leads/...` (intelligence.py) | `prefix="/intelligence"` | `/api/intelligence/leads` |

**Never** add `prefix="/gmail"` to `gmail.py` — its routes already say `/gmail/inbox`,
so you'd get `/api/gmail/gmail/inbox` → 404.

---

## 3. Collision rule (prevents wrong-handler bugs)

If two routers define the **same path+method**, Starlette serves the **first
registered route**. This silently breaks endpoints.

**Known collision to preserve:** `/api/metrics` MUST resolve to the **engagement
report** (`app/api/metrics.py`), NOT the Prometheus text endpoint
(`app/api/v1/health.py`). That is why `metrics_router` is included in
`legacy_router` **before** `health_v1`. Prometheus stays at `/metrics` and
`/api/v1/metrics` (both in the public-path allow-list in `main.py`).

**Rule:** when adding any route that already exists (e.g. `/metrics`,
`/health`), register the intended handler **first** in `legacy_router`, and
keep Prometheus at `/metrics` + `/api/v1/metrics` only.

---

## 4. Cursor rule (prevents `KeyError: 0` / `TypeError`)

`app/database.py` uses **`DictCursor`** (supports BOTH `row[0]` and `row['col']`).
- ✅ `row[0]` works (list index)
- ✅ `row['column']` works (named)
- ❌ `RealDictCursor` only supports `row['col']` → `row[0]` crashes

Do **not** switch `database.py` back to `RealDictCursor`. If a specific query
needs dict access, use `conn.cursor(cursor_factory=psycopg2.extras.DictCursor)`
locally — it still supports `row[0]`.

---

## 5. Verification (run before every PR)

```bash
python scripts/verify_api_contract.py
```

- Exits 0 → no collisions, every frontend `/api/*` path has a route.
- Exits 1 → fix before merging.

CI also runs `scripts/smoke_test.py` which hits every frontend path with a
stubbed DB and asserts HTTP 200 + expected JSON keys.
