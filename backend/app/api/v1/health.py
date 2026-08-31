"""
Health check endpoints for API v1.
"""
from fastapi import APIRouter, Response
from app.core.observability.logging import get_logger
import time

router = APIRouter()
logger = get_logger("health")


@router.get("/health")
async def health_check():
    """Liveness probe - always returns 200 if service is running."""
    return {"status": "healthy", "version": "v1"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe - checks critical dependencies."""
    from app.database import get_db_connection
    import redis
    import os
    import json
    
    checks = {}
    all_healthy = True
    
    # Database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        checks["database"] = "healthy"
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        checks["database"] = "unhealthy"
        all_healthy = False
    
    # Redis
    redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL")
    if redis_url:
        try:
            from app.core.redis_pool import get_redis_client
            r = get_redis_client()
            r.ping()
            checks["redis"] = "healthy"
        except Exception as e:
            logger.warning("Redis health check failed", error=str(e))
            checks["redis"] = "unhealthy"
            # Redis not critical for basic operation
    else:
        checks["redis"] = "not_configured"
    
    # Gmail API
    checks["gmail_api"] = "configured" if os.getenv("GOOGLE_CLIENT_ID") else "not_configured"
    
    # RAG Service
    rag_url = os.getenv("RAG_URL", "https://rag-sys-gz59.onrender.com")
    try:
        import requests
        resp = requests.get(rag_url, timeout=3, verify=True)
        checks["rag_service"] = "healthy" if resp.status_code == 200 else "unhealthy"
    except Exception:
        checks["rag_service"] = "unreachable"
    
    status_code = 200 if all_healthy else 503
    return Response(
        content=json.dumps({"status": "ready" if all_healthy else "not_ready", "checks": checks, "timestamp": time.time()}),
        media_type="application/json",
        status_code=status_code
    )


@router.get("/health/startup")
async def startup_check():
    """Startup probe - for slow-starting containers."""
    return {"status": "started", "migrations": "applied"}


from app.core.responses import JsonObject

@router.get("/health/redis", response_model=JsonObject)
async def redis_check():
    """Redis connection-pool health probe.

    Reports pool utilisation so connection-exhaustion regressions (e.g. the
    historical "max number of clients reached" incident) are caught early.
    """
    import os

    redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL")
    if not redis_url:
        return {"status": "not_configured", "configured": False}

    try:
        from app.core.redis_pool import get_redis_client, get_redis_pool

        client = get_redis_client()
        client.ping()
        pool = get_redis_pool()
        created = getattr(pool, "created_connections", None)
        max_conn = getattr(pool, "max_connections", None)
        in_use = None
        try:
            in_use = len(pool._in_use_connections)  # type: ignore[attr-defined]
        except Exception:
            in_use = None
        return {
            "status": "healthy",
            "configured": True,
            "created_connections": created,
            "max_connections": max_conn,
            "in_use_connections": in_use,
        }
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        return {"status": "unhealthy", "configured": True, "error": str(e)}


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from app.core.observability.metrics import metrics_endpoint
    from fastapi import Response
    return await metrics_endpoint()