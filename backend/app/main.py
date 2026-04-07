from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import os
# Explicitly load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)
# Reload trigger

from app.api import ingest, drafts, dashboard, leads, auth, family_offices, campaigns, users, prompts, admin, companies
from app.database import create_tables

app = FastAPI()

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

from app.api import ingest, drafts, dashboard, leads, auth, family_offices, campaigns, metrics, users, prompts, admin

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
