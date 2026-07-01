from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from pathlib import Path
import os
# Explicitly load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)
# Reload trigger

from app.database import create_tables
from contextlib import asynccontextmanager
import asyncio

async def maintenance_loop():
    from app.services.google_service import renew_all_gmail_watches
    while True:
        try:
            # logger.info("Running background maintenance: Renewing Gmail watches")
            # renew_all_gmail_watches()
            pass
        except Exception as e:
            logger.error(f"Maintenance loop error: {e}")
        await asyncio.sleep(86400) # Run every 24 hours

_scheduler_lock = asyncio.Lock()

async def scheduler_loop():
    from app.services.email_service import check_scheduled_emails
    from app.services.followup_service import process_outreach_sequences
    from app.api.gmail import poll_all_users_for_replies
    while True:
        if _scheduler_lock.locked():
            logger.warning("Scheduler: previous iteration still running, skipping this cycle")
            await asyncio.sleep(10)
            continue
        async with _scheduler_lock:
            try:
                # Move synchronous blocking calls to threads
                # Reply check first, then follow-ups — prevents sending follow-up to someone who already replied
                await asyncio.to_thread(poll_all_users_for_replies)
                await asyncio.to_thread(check_scheduled_emails)
                await asyncio.to_thread(process_outreach_sequences)
            except Exception as e:
                print(f"Scheduler error: {e}")
        await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    t1 = asyncio.create_task(scheduler_loop())
    t2 = asyncio.create_task(maintenance_loop())
    yield
    t1.cancel()
    t2.cancel()

app = FastAPI(lifespan=lifespan)

# Root health check — keeps cron jobs from getting 404
@app.get("/")
def root():
    return {"status": "ok", "message": "LeadStreamAI Backend is running"}

# ---------------------------------------------------------------------------
# CORS — robust multi-origin setup that works on Render with credentials
# ---------------------------------------------------------------------------
# Collect explicit origins (env var is the authoritative source in production)
raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
allowed_origins = [o.strip().rstrip("/") for o in raw_origins.split(",") if o.strip()]

# Always allow local dev + the known deployed frontend
ALWAYS_ALLOWED = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "https://leadstreamai.onrender.com",
]
for o in ALWAYS_ALLOWED:
    if o not in allowed_origins:
        allowed_origins.append(o)

import re as _re
_ONRENDER_RE = _re.compile(r"^https://[a-zA-Z0-9\-]+\.onrender\.com$")

def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in allowed_origins:
        return True
    if _ONRENDER_RE.match(origin):
        return True
    return False

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        is_allowed = _origin_allowed(origin)

        # Handle pre-flight OPTIONS immediately
        if request.method == "OPTIONS":
            resp = StarletteResponse(status_code=204, content="")
            if is_allowed:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Credentials"] = "true"
            else:
                resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            req_hdrs = request.headers.get("Access-Control-Request-Headers", "")
            if req_hdrs:
                resp.headers["Access-Control-Allow-Headers"] = req_hdrs
            else:
                resp.headers["Access-Control-Allow-Headers"] = "*"
            resp.headers["Access-Control-Max-Age"] = "600"
            return resp

        response = await call_next(request)

        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Vary"] = "Origin"
        return response

app.add_middleware(DynamicCORSMiddleware)

from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"VALIDATION ERROR on {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_details = traceback.format_exc()
    logger.error(f"GLOBAL ERROR: {str(exc)}\n{error_details}")
    
    # Get current origins to match CORS
    raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    allowed_origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    reported_origin = "https://leadstreamai.onrender.com"
    if reported_origin not in allowed_origins:
        allowed_origins.append(reported_origin)
    
    origin = request.headers.get("origin")
    response_origin = origin if origin in allowed_origins else "*"

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "message": str(exc),
            "traceback": error_details if os.getenv("DEBUG") == "True" else None
        },
        headers={
            "Access-Control-Allow-Origin": response_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


from fastapi.staticfiles import StaticFiles

# Mount static directory for PDF serving
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

from app.api import ingest, drafts, dashboard, leads, auth, family_offices, campaigns, metrics, users, prompts, admin, companies, rocketreach, gmail, intelligence, admin_dashboard, tracking, reminders

app.include_router(ingest.router, prefix="/api")
app.include_router(drafts.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(family_offices.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(admin.router, prefix="/api", tags=["admin"])
app.include_router(companies.router, prefix="/api", tags=["companies"])
app.include_router(rocketreach.router, prefix="/api", tags=["rocketreach"])
app.include_router(gmail.router, prefix="/api", tags=["gmail"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(tracking.router, prefix="/api", tags=["tracking"])
app.include_router(admin_dashboard.router, prefix="/api/admin", tags=["admin_dashboard"])
app.include_router(reminders.router, prefix="/api", tags=["reminders"])
