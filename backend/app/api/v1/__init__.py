"""
API v1 Router - Versioned API endpoints.
All new endpoints should be added under /api/v1/

Router path rules:
- Routers whose endpoints ALREADY include the resource token (e.g. gmail.py
  defines "/gmail/inbox", dashboard.py defines "/dashboard/stats") are included
  WITHOUT a prefix so they resolve to /api/gmail/inbox, /api/dashboard/stats.
- Routers whose endpoints do NOT include the resource token (auth.py defines
  "/me", "/login"; intelligence.py defines "/leads/...") are included WITH the
  matching prefix (/auth, /intelligence).
"""
from fastapi import APIRouter

# Import v1 routers - use v1 modules
from app.api.v1 import health as health_v1
from app.api import auth
from app.api import leads as leads_v1
from app.api import gmail as gmail_v1
from app.api import drafts as drafts_v1
from app.api import campaigns as campaigns_v1
from app.api import intelligence as intelligence_v1
from app.api import public_email as emails_v1
from app.api import dashboard as dashboard_v1
from app.api import reminders as reminders_v1
from app.api import companies as companies_v1
from app.api import users as users_v1
from app.api import admin as admin_v1
from app.api import admin_dashboard as admin_dashboard_v1
from app.api import family_offices as family_offices_v1
from app.api import generate as generate_v1
from app.api import ingest as ingest_v1
from app.api import prompts as prompts_v1
from app.api import rocketreach as rocketreach_v1
from app.api import tracking as tracking_v1
from app.api import metrics as metrics_router

api_v1_router = APIRouter(prefix="/api/v1")

# Health endpoints (no auth required)
api_v1_router.include_router(health_v1.router, tags=["health"])

# Auth endpoints (endpoints are /me, /login -> prefix /auth)
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Lead management (endpoints already /leads/* -> no prefix)
api_v1_router.include_router(leads_v1.router, tags=["leads"])

# Gmail integration (endpoints already /gmail/* -> no prefix)
api_v1_router.include_router(gmail_v1.router, tags=["gmail"])

# Email drafts (endpoints already /emails, /signatures, /generate-draft -> no prefix)
api_v1_router.include_router(drafts_v1.router, tags=["drafts"])

# Campaigns (endpoints already /campaigns/* -> no prefix)
api_v1_router.include_router(campaigns_v1.router, tags=["campaigns"])

# AI Intelligence (endpoints /leads/*, /chat/* -> prefix /intelligence)
api_v1_router.include_router(intelligence_v1.router, prefix="/intelligence", tags=["intelligence"])

# Public email (unsubscribe/resubscribe/preferences already at root -> no prefix)
api_v1_router.include_router(emails_v1.router, tags=["public_email"])

# Dashboard (endpoints already /dashboard/* -> no prefix)
api_v1_router.include_router(dashboard_v1.router, tags=["dashboard"])

# Reminders (endpoints already /reminders/* -> no prefix)
api_v1_router.include_router(reminders_v1.router, tags=["reminders"])

# Companies (endpoints already /companies/* -> no prefix)
api_v1_router.include_router(companies_v1.router, tags=["companies"])

# Users (endpoints already /users/* -> no prefix)
api_v1_router.include_router(users_v1.router, tags=["users"])

# Admin (endpoints already /admin/* -> no prefix)
api_v1_router.include_router(admin_v1.router, tags=["admin"])

# Admin dashboard (endpoints /leads/*, /stats/* -> prefix /admin)
api_v1_router.include_router(admin_dashboard_v1.router, prefix="/admin", tags=["admin"])

# Family offices (endpoints already /family-offices/* -> no prefix)
api_v1_router.include_router(family_offices_v1.router, tags=["family_offices"])

# Generate (endpoints already /generate/* -> no prefix)
api_v1_router.include_router(generate_v1.router, tags=["generate"])

# Ingest (endpoints already /ingest-leads -> no prefix)
api_v1_router.include_router(ingest_v1.router, tags=["ingest"])

# Prompts (endpoints already /prompts/* -> no prefix)
api_v1_router.include_router(prompts_v1.router, tags=["prompts"])

# Rocketreach (endpoints already /rocketreach/* -> no prefix)
api_v1_router.include_router(rocketreach_v1.router, tags=["rocketreach"])

# Tracking pixels (endpoints already /track/* -> no prefix)
api_v1_router.include_router(tracking_v1.router, tags=["tracking"])


# Legacy API v0 router for backward compatibility
# Maps old /api/* routes to v1 equivalents
legacy_router = APIRouter(prefix="/api")

# Include all v1 routes under legacy prefix for backward compatibility
# NOTE: the engagement REPORT router must be registered BEFORE health_v1 so that
# /api/metrics serves the JSON report (Metrics.jsx / MisReportPage.jsx) rather
# than the Prometheus text endpoint that health_v1 also exposes at /metrics.
legacy_router.include_router(metrics_router.router, tags=["metrics"])
legacy_router.include_router(health_v1.router, tags=["health"])
legacy_router.include_router(auth.router, prefix="/auth", tags=["auth"])
legacy_router.include_router(leads_v1.router, tags=["leads"])
legacy_router.include_router(gmail_v1.router, tags=["gmail"])
legacy_router.include_router(drafts_v1.router, tags=["drafts"])
legacy_router.include_router(campaigns_v1.router, tags=["campaigns"])
legacy_router.include_router(intelligence_v1.router, prefix="/intelligence", tags=["intelligence"])
legacy_router.include_router(emails_v1.router, tags=["public_email"])
legacy_router.include_router(dashboard_v1.router, tags=["dashboard"])
legacy_router.include_router(reminders_v1.router, tags=["reminders"])
legacy_router.include_router(companies_v1.router, tags=["companies"])
legacy_router.include_router(users_v1.router, tags=["users"])
legacy_router.include_router(admin_v1.router, tags=["admin"])
legacy_router.include_router(admin_dashboard_v1.router, prefix="/admin", tags=["admin"])
legacy_router.include_router(family_offices_v1.router, tags=["family_offices"])
legacy_router.include_router(generate_v1.router, tags=["generate"])
legacy_router.include_router(ingest_v1.router, tags=["ingest"])
legacy_router.include_router(prompts_v1.router, tags=["prompts"])
legacy_router.include_router(rocketreach_v1.router, tags=["rocketreach"])
legacy_router.include_router(tracking_v1.router, tags=["tracking"])
