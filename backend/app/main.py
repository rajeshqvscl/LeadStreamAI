from fastapi import FastAPI, Request, Form
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

# Public unsubscribe endpoint — token-based, no auth required
# Step 7: Confirmation page — prevents accidental unsubscribe from bot/scanner prefetch
@app.get("/unsubscribe")
async def unsubscribe_get(token: str, request: Request):
    logger.info(f"Unsubscribe GET request: token={token}, url={request.url}, referer={request.headers.get('referer')}, ua={request.headers.get('user-agent')}, origin={request.headers.get('origin')}")
    from app.api.leads import validate_unsubscribe_token, process_unsubscribe_by_token
    try:
        lead = validate_unsubscribe_token(token)
    except Exception:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="""
            <div style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #dc2626;">Invalid Link</h1>
                <p>This unsubscribe link is invalid or expired.</p>
            </div>
        """, status_code=404, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})

    already_unsubscribed = lead.get('email_opt_in') is False or lead.get('is_unsubscribed') is True
    if already_unsubscribed:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="""
            <div style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #6366f1;">Already Unsubscribed</h1>
                <p>You have already been removed from our outreach list.</p>
            </div>
        """, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})

    from fastapi.responses import HTMLResponse
    base = str(request.base_url).rstrip("/")
    return HTMLResponse(
        content=f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 60px auto; padding: 32px; text-align: center; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h1 style="color: #1e293b; font-size: 22px; margin-bottom: 8px;">LeadStream</h1>
            <p style="color: #64748b; font-size: 15px; margin-bottom: 24px;">Do you want to stop receiving automated emails?</p>
            <form action="{base}/unsubscribe/confirm" method="POST" style="display: inline-block; margin-right: 12px;">
                <input type="hidden" name="token" value="{token}">
                <button type="submit" style="background: #6366f1; color: white; border: none; padding: 10px 24px; border-radius: 8px; font-size: 14px; cursor: pointer; font-weight: 500;">Unsubscribe</button>
            </form>
            <form action="{base}/unsubscribe/keep" method="GET" style="display: inline-block;">
                <input type="hidden" name="token" value="{token}">
                <button type="submit" style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; padding: 10px 24px; border-radius: 8px; font-size: 14px; cursor: pointer; font-weight: 500;">Keep Me Subscribed</button>
            </form>
        </div>
        """,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
    )

@app.post("/unsubscribe/confirm")
async def unsubscribe_confirm(token: str = Form(...), request: Request = None):
    logger.info(f"Unsubscribe CONFIRM: token={token}, referer={request.headers.get('referer') if request else 'N/A'}, origin={request.headers.get('origin') if request else 'N/A'}")
    from app.api.leads import process_unsubscribe_by_token
    process_unsubscribe_by_token(token)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content="""
        <div style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #6366f1;">Unsubscribe Successful</h1>
            <p>You have been successfully removed from our outreach list.</p>
            <p style="color: #64748b; font-size: 14px;">You will no longer receive automated emails.</p>
        </div>
    """, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})

@app.get("/unsubscribe/keep")
async def unsubscribe_keep(token: str):
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content="""
        <div style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #16a34a;">You're Still Subscribed</h1>
            <p>You have not been unsubscribed. You will continue to receive our emails.</p>
        </div>
    """, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})

# RFC 8058 one-click unsubscribe — email clients POST directly (immediate, no confirmation)
@app.post("/unsubscribe")
async def unsubscribe_post(token: str, request: Request = None):
    logger.info(f"Unsubscribe POST (one-click): token={token}, referer={request.headers.get('referer') if request else 'N/A'}, origin={request.headers.get('origin') if request else 'N/A'}")
    from app.api.leads import process_unsubscribe_by_token
    process_unsubscribe_by_token(token)
    from fastapi.responses import Response
    return Response(status_code=200, content="ok", headers={"Cache-Control": "no-store"})

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
    "http://localhost:5713",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5713",
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

from app.api import ingest, drafts, dashboard, leads, auth, family_offices, campaigns, metrics, users, prompts, admin, companies, rocketreach, gmail, intelligence, admin_dashboard, tracking, reminders, public_email

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
app.include_router(public_email.router)
