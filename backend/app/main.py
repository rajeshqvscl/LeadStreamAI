from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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

async def scheduler_loop():
    from app.services.email_service import check_scheduled_emails
    from app.services.followup_service import process_outreach_sequences
    from app.api.gmail import poll_all_users_for_replies
    while True:
        try:
            check_scheduled_emails()
            # process_outreach_sequences()
            # poll_all_users_for_replies()
            pass
        except Exception:
            pass
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    t1 = asyncio.create_task(scheduler_loop())
    t2 = asyncio.create_task(maintenance_loop())
    yield
    t1.cancel()
    t2.cancel()

app = FastAPI(lifespan=lifespan)

# Get allowed origins from environment variable
raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
# Parse and clean origins
allowed_origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]

# Always include default dev origins for local testing
dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
for d in dev_origins:
    if d not in allowed_origins:
        allowed_origins.append(d)

# Include the reported frontend URL
reported_origin = "https://lead-frontend-5new.onrender.com"
if reported_origin not in allowed_origins:
    allowed_origins.append(reported_origin)

# Initialize database
create_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_details = traceback.format_exc()
    logger.error(f"GLOBAL ERROR: {str(exc)}\n{error_details}")
    
    # Get current origins to match CORS
    raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    allowed_origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    reported_origin = "https://lead-frontend-5new.onrender.com"
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

from app.api import ingest, drafts, dashboard, leads, auth, family_offices, campaigns, metrics, users, prompts, admin, companies, rocketreach, gmail, intelligence, admin_dashboard

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
app.include_router(admin_dashboard.router, prefix="/api/admin", tags=["admin_dashboard"])
