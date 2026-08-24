from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse
import logging

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from pathlib import Path
import os
# Load environment variables (authoritative source)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.database import create_tables
from contextlib import asynccontextmanager
import asyncio

from app.core.pipeline.scheduler import get_scheduler_config

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
    
    config = get_scheduler_config()
    
    # Track last run times
    last_followup = 0
    last_scheduled = 0
    last_reply_poll = 0
    
    while True:
        if _scheduler_lock.locked():
            logger.warning("Scheduler: previous iteration still running, skipping this cycle")
            await asyncio.sleep(2)
            continue
        
        now = asyncio.get_event_loop().time()
        async with _scheduler_lock:
            try:
                tasks = []
                
                # Follow-ups: every FOLLOWUP_INTERVAL
                if now - last_followup >= config.followup_interval_sec:
                    tasks.append(("followup", asyncio.to_thread(process_outreach_sequences)))
                    last_followup = now
                
                # Scheduled emails: every SCHEDULED_INTERVAL
                if now - last_scheduled >= config.scheduled_interval_sec:
                    tasks.append(("scheduled", asyncio.to_thread(check_scheduled_emails)))
                    last_scheduled = now
                
                # Reply polling: every REPLY_POLL_INTERVAL
                if now - last_reply_poll >= config.reply_poll_interval_sec:
                    tasks.append(("replies", asyncio.to_thread(poll_all_users_for_replies)))
                    last_reply_poll = now
                
                if tasks:
                    # Run selected tasks in parallel
                    results = await asyncio.gather(
                        *[task[1] for task in tasks],
                        return_exceptions=True,
                    )
                    # Log any exceptions
                    for (name, _), r in zip(tasks, results):
                        if isinstance(r, Exception):
                            logger.error(f"Scheduler task '{name}' error: {r}")
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(2)

async def reply_cleanup_loop():
    """
    Runs the reply-monitoring job twice a day (configurable hours IST):
      - deletes remaining generated follow-ups for replied leads
      - sends the admin email report + in-app reminder notification
    The loop sleeps precisely until the next scheduled slot.
    """
    from datetime import datetime, timedelta, timezone
    from app.core.pipeline.scheduler import get_scheduler_config
    
    config = get_scheduler_config()
    IST = timezone(timedelta(hours=5, minutes=30))
    cleanup_hours = config.get_reply_cleanup_hours()
    
    while True:
        try:
            now = datetime.now(IST)
            candidates = [
                datetime(now.year, now.month, now.day, h, 0, 0, tzinfo=IST)
                for h in cleanup_hours
            ]
            future = [c for c in candidates if c > now]
            next_run = min(future) if future else candidates[0] + timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(
                "Reply monitor: next cleanup at %s IST (in %.1f h)",
                next_run.strftime("%d %b %Y %I:%M %p"),
                wait_seconds / 3600,
            )
            await asyncio.sleep(wait_seconds)
            from app.services.reply_cleanup_service import run_daily_reply_cleanup_and_report
            await asyncio.to_thread(run_daily_reply_cleanup_and_report)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Reply monitor loop error: {e}")
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        create_tables()
    except Exception as e:
        logger.error(f"Failed to create/verify tables on startup: {e}")
        logger.warning("App will still start — DB may be temporarily unavailable")
    
    # Start email engine dispatcher
    email_dispatcher = None
    try:
        from app.email_engine.worker.pool import get_dispatcher
        email_dispatcher = get_dispatcher()
        email_dispatcher.start()
        logger.info("Email engine dispatcher started")
    except Exception as e:
        logger.warning(f"Could not start email dispatcher: {e}")
    
    t1 = asyncio.create_task(scheduler_loop())
    t2 = asyncio.create_task(maintenance_loop())
    t3 = asyncio.create_task(reply_cleanup_loop())
    yield
    t1.cancel()
    t2.cancel()
    t3.cancel()
    
    # Stop email dispatcher
    if email_dispatcher:
        email_dispatcher.stop()
        logger.info("Email engine dispatcher stopped")

app = FastAPI(lifespan=lifespan)

# Root health check — keeps cron jobs from getting 404
@app.get("/")
def root():
    return {"status": "ok", "message": "LeadStreamAI Backend is running"}

# Debug endpoint — only available when DEBUG=True
@app.get("/debug/unsubscribe-env")
def debug_unsubscribe_env():
    if os.getenv("DEBUG", "").lower() not in ("true", "1", "yes"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return {
        "BACKEND_URL": os.getenv("BACKEND_URL", "NOT SET"),
        "FRONTEND_URL": os.getenv("FRONTEND_URL", "NOT SET"),
        "VITE_API_BASE_URL": os.getenv("VITE_API_BASE_URL", "NOT SET"),
        "RENDER_EXTERNAL_URL": os.getenv("RENDER_EXTERNAL_URL", "NOT SET"),
    }

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
                req_hdrs = request.headers.get("Access-Control-Request-Headers", "")
                resp.headers["Access-Control-Allow-Headers"] = req_hdrs or "Content-Type, Authorization, X-User-Id"
                resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                resp.headers["Access-Control-Max-Age"] = "600"
            return resp

        response = await call_next(request)

        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            req_hdrs = request.headers.get("Access-Control-Request-Headers", "")
            response.headers["Access-Control-Allow-Headers"] = req_hdrs or "Content-Type, Authorization, X-User-Id"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Vary"] = "Origin"
        return response

# (CORS is registered at the END of the AUTH MIDDLEWARE section below so it
# is OUTERMOST — see the ordering note there.)

# ---------------------------------------------------------------------------
# AUTH MIDDLEWARE — real session-token verification
# ---------------------------------------------------------------------------
# The frontend attaches `Authorization: Bearer <token>`. Every request to a
# protected /api route must carry a valid session token created at login.
# The verified user_id from the session REPLACES any client-supplied
# X-User-Id header, so header spoofing (the old auth hole) is impossible.
#
# Public paths (no auth): login, Google OAuth callback, Gmail Pub/Sub
# webhook, email tracking pixels, unsubscribe/resubscribe pages, static
# assets, and the one-click admin approve landing page.

_PUBLIC_PATH_EXACT = {"/"}

_PUBLIC_PATH_PREFIXES = (
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/google/callback",
    "/api/gmail/pubsub-push",
    "/api/track/",
    "/api/unsubscribe",
    "/api/resubscribe",
    "/api/preferences",
    "/api/admin/approve-user/",
    "/unsubscribe",
    "/resubscribe",
    "/preferences",
    "/static/",
    "/assets/",
    "/debug/",
)


def _verify_session(token: str):
    """Returns the verified user_id for a valid, unexpired session token, else None."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id FROM sessions WHERE token = %s AND expires_at > NOW()",
                (token,),
            )
            row = cur.fetchone()
            return row["user_id"] if row else None
        finally:
            cur.close()
            conn.close()
    except Exception:
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # CORS preflight never carries credentials — let it through
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATH_EXACT or path.startswith(_PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        token = None
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

        if not token:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        user_id = await asyncio.to_thread(_verify_session, token)
        if not user_id:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired session. Please log in again."})

        # Override any client-supplied X-User-Id with the verified session user
        request.scope["headers"] = [
            (k, v) if k.lower() != b"x-user-id" else (b"x-user-id", str(user_id).encode())
            for k, v in request.scope["headers"]
        ]
        request.state.user_id = str(user_id)
        return await call_next(request)


# Middleware order matters: Starlette's add_middleware inserts at position 0,
# so the LAST registered middleware is OUTERMOST. Auth is registered FIRST
# (inner); CORS is registered LAST (outermost) so that 401 responses raised by
# AuthMiddleware still flow back through CORS and get CORS headers — otherwise
# the browser would block them and the frontend's 401 interceptor could never
# read the response to clear the stale token.
app.add_middleware(AuthMiddleware)
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
    
    # Use same CORS logic as DynamicCORSMiddleware
    origin = request.headers.get("origin", "")
    headers = {}
    if _origin_allowed(origin):
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-User-Id",
        }

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "message": str(exc),
            "traceback": error_details if os.getenv("DEBUG") == "True" else None
        },
        headers=headers
    )


from fastapi.staticfiles import StaticFiles

# Ensure .webp assets are served with the correct image/webp content type.
# Starlette's StaticFiles falls back to Python's mimetypes registry, which on
# some systems (Windows, minimal Linux containers) does NOT know .webp — the
# file then goes out as application/octet-stream and browsers/email clients
# refuse to render it (exactly what broke Palak's logo). Registering the type
# here (before the mounts below) makes every .webp upload render correctly.
import mimetypes
if mimetypes.guess_type("x.webp")[0] != "image/webp":
    mimetypes.add_type("image/webp", ".webp")

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
