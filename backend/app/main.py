import os
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load environment variables (authoritative source)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configure structured logging
from app.core.observability.logging import configure_logging
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_output=os.getenv("LOG_FORMAT", "json").lower() == "json",
)

import logging
logger = logging.getLogger(__name__)

from app.core.pipeline.scheduler import get_scheduler_config
from app.database import create_tables
from app.core.rate_limiter import get_rate_limiter, RateLimitMiddleware


async def maintenance_loop():
    """
    Runs maintenance tasks at fixed IST hours (default 8 AM and 8 PM),
    Monday–Saturday only.

    The actual work (renew Gmail watches, cache cleanup, etc.) is a no-op
    placeholder for now; only the scheduling window is enforced so it can be
    wired up later without touching the loop logic.
    """
    from datetime import datetime, timedelta, timezone

    from app.core.pipeline.scheduler import get_scheduler_config

    config = get_scheduler_config()
    IST = timezone(timedelta(hours=5, minutes=30))
    maint_hours = config.get_maintenance_hours()
    maint_days = config.get_maintenance_days()

    while True:
        try:
            now = datetime.now(IST)
            # Skip on off-days (outside Mon–Sat)
            if now.weekday() not in maint_days:
                # Wait until the next Monday at the first maintenance hour
                days_to_monday = (7 - now.weekday()) % 7 or 7
                next_run = (now + timedelta(days=days_to_monday)).replace(
                    hour=maint_hours[0], minute=0, second=0, microsecond=0
                )
                wait_seconds = (next_run - now).total_seconds()
                logger.info(
                    "Maintenance: off-day skip, next run %s IST (in %.1f h)",
                    next_run.strftime("%d %b %Y %I:%M %p"),
                    wait_seconds / 3600,
                )
                await asyncio.sleep(wait_seconds)
                continue

            candidates = [
                datetime(now.year, now.month, now.day, h, 0, 0, tzinfo=IST)
                for h in maint_hours
            ]
            future = [c for c in candidates if c > now]
            next_run = min(future) if future else candidates[0] + timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(
                "Maintenance: next run at %s IST (in %.1f h)",
                next_run.strftime("%d %b %Y %I:%M %p"),
                wait_seconds / 3600,
            )
            await asyncio.sleep(wait_seconds)
            # Run the actual maintenance work.
            try:
                # renew_all_gmail_watches()
                pass
            except Exception as e:
                logger.exception(f"Maintenance task error: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Maintenance loop error: {e}")
            await asyncio.sleep(60)

_scheduler_lock = asyncio.Lock()

async def scheduler_loop():
    from app.services.email_service import check_scheduled_emails, process_auto_pilot_sweep
    from app.services.followup_service import process_outreach_sequences

    config = get_scheduler_config()

    # Track last run times
    last_followup = 0
    last_scheduled = 0
    last_autopilot = 0

    # Startup cooldown: keep ALL automated dispatch paused for the first
    # `scheduler_startup_cooldown_sec` seconds after boot. This guarantees that
    # any drafts created right before/after a restart stay in the review queue
    # (PENDING_APPROVAL) long enough for a human to manually send or reject them
    # before the auto-pilot sweep promotes them to SCHEDULED.
    loop_start = asyncio.get_event_loop().time()
    cooldown_sec = config.scheduler_startup_cooldown_sec
    _last_cd_log = cooldown_sec + 1  # force the first cooldown log

    while True:
        if _scheduler_lock.locked():
            logger.warning("Scheduler: previous iteration still running, skipping this cycle")
            await asyncio.sleep(2)
            continue

        now = asyncio.get_event_loop().time()

        # Startup cooldown gate — skip ALL automated work while active.
        if (now - loop_start) < cooldown_sec:
            remaining = int(cooldown_sec - (now - loop_start))
            if remaining <= _last_cd_log - 30 or remaining <= 5:
                logger.info(
                    f"Scheduler: startup cooldown active — {remaining}s remaining, "
                    f"drafts held in review queue"
                )
                _last_cd_log = remaining
            await asyncio.sleep(2)
            continue

        async with _scheduler_lock:
            try:
                # Check if it's weekend (Saturday=5, Sunday=6)
                from datetime import datetime, timezone, timedelta
                IST = timezone(timedelta(hours=5, minutes=30))
                now_ist = datetime.now(IST)
                if now_ist.weekday() >= 5:
                    # Weekend - skip this cycle
                    await asyncio.sleep(config.followup_interval_sec)
                    continue

                tasks = []

                # Follow-ups: every FOLLOWUP_INTERVAL
                if now - last_followup >= config.followup_interval_sec:
                    tasks.append(("followup", asyncio.to_thread(process_outreach_sequences)))
                    last_followup = now

                # Scheduled emails: every SCHEDULED_INTERVAL
                if now - last_scheduled >= config.scheduled_interval_sec:
                    tasks.append(("scheduled", asyncio.to_thread(check_scheduled_emails)))
                    last_scheduled = now

                # Auto-pilot sweep: pick up review-queue drafts every ~5 min
                if now - last_autopilot >= 300:
                    tasks.append(("autopilot", asyncio.to_thread(process_auto_pilot_sweep)))
                    last_autopilot = now

                if tasks:
                    # Run selected tasks in parallel
                    results = await asyncio.gather(
                        *[task[1] for task in tasks],
                        return_exceptions=True,
                    )
                    # Log any exceptions
                    for (name, _), r in zip(tasks, results, strict=False):
                        if isinstance(r, Exception):
                            logger.error(f"Scheduler task '{name}' error: {r}")
            except Exception as e:
                logger.exception(f"Scheduler error: {e}")
        await asyncio.sleep(2)

async def reply_cleanup_loop():
    """
    Runs the reply-monitoring job twice a day (configurable hours IST):
      - deletes remaining generated follow-ups for replied leads
      - sends the admin email report + in-app reminder notification
    The loop sleeps precisely until the next scheduled slot.
    Skips weekends (Saturday/Sunday).
    """
    from datetime import datetime, timedelta, timezone

    from app.core.pipeline.scheduler import get_scheduler_config

    config = get_scheduler_config()
    IST = timezone(timedelta(hours=5, minutes=30))
    cleanup_hours = config.get_reply_cleanup_hours()

    while True:
        try:
            now = datetime.now(IST)
            # Skip cleanup on weekends (Sat=5, Sun=6)
            if now.weekday() >= 5:
                # Calculate wait until Monday at first cleanup hour
                days_to_monday = 7 - now.weekday()
                next_monday = (now + timedelta(days=days_to_monday)).replace(
                    hour=cleanup_hours[0], minute=0, second=0, microsecond=0
                )
                wait_seconds = (next_monday - now).total_seconds()
                logger.info(f"Reply cleanup: weekend skip, next run Monday at {next_monday.strftime('%I:%M %p')} IST (in {wait_seconds/3600:.1f} h)")
                await asyncio.sleep(wait_seconds)
                continue

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
            logger.exception(f"Reply monitor loop error: {e}")
            await asyncio.sleep(60)

async def reply_polling_loop():
    """
    Runs the Gmail reply detector at fixed IST hours (default 9 AM, 1 PM, 5 PM).
    Replaces the old continuous 30s polling — ~97% less Gmail API quota usage.
    Pub/Sub push still provides real-time detection when configured; this loop
    is the reliable fallback. Manual /gmail/sync-inbound remains available.

    Startup catch-up: if the most recent passed slot was missed <2 hours ago
    (e.g. server restart), poll immediately once so replies aren't delayed.
    """
    from datetime import datetime, timedelta, timezone

    from app.api.gmail import poll_all_users_for_replies
    from app.core.pipeline.scheduler import get_scheduler_config

    config = get_scheduler_config()
    IST = timezone(timedelta(hours=5, minutes=30))
    CATCHUP_WINDOW_HOURS = 2

    # Startup catch-up: run once if we're just past a missed slot
    try:
        now = datetime.now(IST)
        # Skip catch-up on weekends
        if now.weekday() < 5:
            for h in sorted(config.get_reply_poll_hours(), reverse=True):
                slot = now.replace(hour=h, minute=0, second=0, microsecond=0)
                if slot <= now and (now - slot) <= timedelta(hours=CATCHUP_WINDOW_HOURS):
                    logger.info(f"Reply polling: catching up on {h}:00 IST slot")
                    # Run in thread with error handling
                    try:
                        await asyncio.to_thread(poll_all_users_for_replies)
                    except Exception as e:
                        logger.exception(f"Reply polling catch-up error: {e}")
                    break
    except Exception as e:
        logger.exception(f"Reply polling catch-up setup error: {e}")

    while True:
        try:
            now = datetime.now(IST)
            # Skip polling on weekends (Sat=5, Sun=6)
            if now.weekday() >= 5:
                # Calculate wait until Monday 9 AM
                days_to_monday = 7 - now.weekday()
                next_monday = (now + timedelta(days=days_to_monday)).replace(
                    hour=config.get_reply_poll_hours()[0], minute=0, second=0, microsecond=0
                )
                wait_seconds = (next_monday - now).total_seconds()
                logger.info(f"Reply polling: weekend skip, next run Monday at {next_monday.strftime('%I:%M %p')} IST (in {wait_seconds/3600:.1f} h)")
                await asyncio.sleep(wait_seconds)
                continue

            candidates = [
                datetime(now.year, now.month, now.day, h, 0, 0, tzinfo=IST)
                for h in config.get_reply_poll_hours()
            ]
            future = [c for c in candidates if c > now]
            next_run = min(future) if future else candidates[0] + timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(
                "Reply polling: next run at %s IST (in %.1f h)",
                next_run.strftime("%d %b %Y %I:%M %p"),
                wait_seconds / 3600,
            )
            await asyncio.sleep(wait_seconds)
            
            # Run polling in thread with error handling
            try:
                await asyncio.to_thread(poll_all_users_for_replies)
            except Exception as e:
                logger.exception(f"Reply polling error: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Reply polling loop error: {e}")
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        create_tables()
    except Exception as e:
        logger.exception(f"Failed to create/verify tables on startup: {e}")
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
    t4 = asyncio.create_task(reply_polling_loop())
    yield
    t1.cancel()
    t2.cancel()
    t3.cancel()
    t4.cancel()

    # Stop email dispatcher
    if email_dispatcher:
        email_dispatcher.stop()
        logger.info("Email engine dispatcher stopped")

app = FastAPI(lifespan=lifespan)


@app.get("/")
@app.head("/")
async def root():
    """Health check endpoint — Render sends HEAD / on startup."""
    return {"status": "ok"}


@app.get("/healthz")
@app.head("/healthz")
async def healthz():
    """Dedicated liveness probe — avoids SPA catch-all interference."""
    return {"status": "ok"}


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    from app.core.observability.metrics import metrics_endpoint
    return await metrics_endpoint()

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
    from app.api.leads import validate_unsubscribe_token
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
    return bool(_ONRENDER_RE.match(origin))

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
    "/unsubscribe",
    "/resubscribe",
    "/preferences",
    "/static/",
    "/assets/",
    "/debug/",
    "/health",
    "/healthz",
    "/metrics",
    "/openapi.json",
    "/api/health",
    "/api/v1/health",
    "/api/v1/metrics",
    "/api/health/ready",
    "/api/v1/health/ready",
    "/api/health/startup",
    "/api/v1/health/startup",
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
        # Registration (POST /api/users/) must be publicly accessible, but other
        # /api/users/* methods (list/update/delete) stay protected.
        if path == "/api/users/" and request.method == "POST":
            return await call_next(request)
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


import uuid as _uuid
import time as _time
import structlog
import structlog.contextvars as _ctx_vars

_corr_log = structlog.get_logger("correlation")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation/request ID to every request, bind it to the
    structured-log context, and echo it back in the response headers so
    failures can be traced end-to-end (observability)."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or _uuid.uuid4().hex
        _ctx_vars.bind_contextvars(request_id=rid)
        request.state.request_id = rid
        start = _time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _ctx_vars.unbind_contextvars("request_id", "user_id")
            raise
        latency_ms = (_time.perf_counter() - start) * 1000.0
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            _ctx_vars.bind_contextvars(user_id=str(user_id))
        response.headers["X-Request-ID"] = rid
        _corr_log.info(
            "request_completed",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            latency_ms=round(latency_ms, 2),
        )
        _ctx_vars.unbind_contextvars("request_id", "user_id")
        return response


# Middleware order matters: Starlette's add_middleware inserts at position 0,
# so the LAST registered middleware is OUTERMOST. 
# Order (outer to inner): CorrelationId -> CORS -> Prometheus -> RateLimit -> Auth
# CorrelationId is outermost so it wraps every request (and is echoed to clients).
app.add_middleware(AuthMiddleware)
# Add rate limiting middleware (uses Redis-backed sliding window)
try:
    rate_limiter = get_rate_limiter()
    app.add_middleware(RateLimitMiddleware, limiter=rate_limiter, default_limit=100, default_window=60)
    logger.info("Rate limiting middleware enabled")
except Exception as e:
    logger.warning(f"Rate limiting disabled: {e}")

# Add Prometheus metrics middleware
try:
    from app.core.observability.metrics import PrometheusMiddleware
    app.add_middleware(PrometheusMiddleware)
    logger.info("Prometheus metrics middleware enabled")
except Exception as e:
    logger.warning(f"Prometheus metrics disabled: {e}")

app.add_middleware(DynamicCORSMiddleware)

# CorrelationId middleware MUST be the LAST registered (outermost) so it
# surrounds CORS/Auth/rate-limit and binds request_id for the whole request.
app.add_middleware(CorrelationIdMiddleware)

from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"VALIDATION ERROR on {request.url}: {exc.errors()}")
    # exc.body can be a non-JSON-serializable object (e.g. FormData for file
    # uploads); coerce it so this handler never crashes while reporting a 422.
    try:
        import json as _json
        _json.dumps(exc.body)
        body = exc.body
    except TypeError:
        body = str(exc.body)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": body}
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


# Import v1 API router (primary) and legacy router (backward compatibility)
from app.api.v1 import api_v1_router, legacy_router

# Include v1 API (primary) - new endpoints should use /api/v1/
app.include_router(api_v1_router)

# Include legacy API for backward compatibility - maps /api/* to v1
app.include_router(legacy_router)

# Ensure .webp assets are served with the correct image/webp content type.
# Starlette's StaticFiles falls back to Python's mimetypes registry, which on
# some systems (Windows, minimal Linux containers) does NOT know .webp — the
# file then goes out as application/octet-stream and browsers/email clients
# refuse to render it (exactly what broke Palak's logo). Registering the type
# here (before the mounts below) makes every .webp upload render correctly.
import mimetypes

from fastapi.staticfiles import StaticFiles

if mimetypes.guess_type("x.webp")[0] != "image/webp":
    mimetypes.add_type("image/webp", ".webp")

# Mount static directory for PDF serving
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# Mount frontend SPA (React build) as catch-all for non-API routes
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
