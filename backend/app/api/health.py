"""
Health Check Endpoints
Provides liveness, readiness, and startup probes for Kubernetes/Render.
"""
import logging
import os
import time

import redis
from app.database import get_db_connection
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def liveness_check():
    """
    Liveness probe - returns 200 if process is alive.
    Does NOT check dependencies - just confirms the app is running.
    """
    return {"status": "alive", "service": "leadstreamai-backend"}


@router.get("/ready")
async def readiness_check():
    """
    Readiness probe - returns 200 if app can serve traffic.
    Checks critical dependencies: Database, Redis.
    Returns 503 if any critical dependency is unavailable.
    """
    checks = {}
    all_healthy = True

    # Check Database
    db_start = time.time()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        checks["database"] = {
            "status": "healthy",
            "latency_ms": round((time.time() - db_start) * 1000, 2)
        }
    except Exception as e:
        logger.exception(f"Database health check failed: {e}")
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False

    # Check Redis
    redis_start = time.time()
    redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL")
    if redis_url:
        try:
            r = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            r.ping()
            checks["redis"] = {
                "status": "healthy",
                "latency_ms": round((time.time() - redis_start) * 1000, 2)
            }
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            checks["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            # Redis is not critical for basic operation
            # all_healthy = False
    else:
        checks["redis"] = {
            "status": "not_configured",
            "note": "REDIS_URL not set"
        }

    # Check Gmail API configuration
    checks["gmail_api"] = {
        "status": "configured" if os.getenv("GOOGLE_CLIENT_ID") else "not_configured"
    }

    # Check RAG service (optional)
    rag_url = os.getenv("RAG_URL", "https://rag-sys-gz59.onrender.com")
    rag_start = time.time()
    try:
        import requests
        resp = requests.get(rag_url, timeout=3, verify=True)
        checks["rag_service"] = {
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "latency_ms": round((time.time() - rag_start) * 1000, 2)
        }
    except Exception as e:
        checks["rag_service"] = {
            "status": "unreachable",
            "error": str(e)[:100]
        }

    status_code = 200 if all_healthy else 503
    return {
        "status": "ready" if all_healthy else "not_ready",
        "service": "leadstreamai-backend",
        "checks": checks,
        "timestamp": time.time()
    }, status_code


@router.get("/startup")
async def startup_check():
    """
    Startup probe - for slow-starting containers.
    Returns 200 once the app has completed initialization.
    """
    # Check if database migrations are up to date
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM alembic_version")
        cur.fetchone()
        cur.close()
        conn.close()
        return {"status": "started", "migrations": "applied"}
    except Exception as e:
        logger.warning(f"Startup check - migrations may not be applied: {e}")
        return {"status": "starting", "migrations": "pending", "note": str(e)}, 200


@router.get("/metrics")
async def metrics_endpoint():
    """
    Basic metrics endpoint for Prometheus scraping.
    Returns key application metrics in Prometheus format.
    """
    metrics = []

    # Database connection pool stats (if available)
    metrics.append("# HELP leadstreamai_info Application info")
    metrics.append("# TYPE leadstreamai_info gauge")
    metrics.append('leadstreamai_info{version="1.0.0"} 1')

    # Add more metrics as needed
    return "\n".join(metrics) + "\n"
