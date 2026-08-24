"""
Redis Connection Pool for Email Engine
Singleton pattern for connection reuse.
"""

import redis
from typing import Optional
from app.core.config import get_email_engine_settings
import logging

logger = logging.getLogger(__name__)

_pool: Optional[redis.ConnectionPool] = None
_client: Optional[redis.Redis] = None


def get_redis_pool() -> redis.ConnectionPool:
    """Get or create Redis connection pool"""
    global _pool
    if _pool is None:
        settings = get_email_engine_settings()
        _pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        logger.info(f"Created Redis connection pool: {settings.redis_url}")
    return _pool


def get_redis_client() -> redis.Redis:
    """Get Redis client from pool"""
    global _client
    if _client is None:
        _client = redis.Redis(connection_pool=get_redis_pool())
    return _client


def close_redis_pool():
    """Close connection pool (for graceful shutdown)"""
    global _pool, _client
    if _client:
        _client.close()
        _client = None
    if _pool:
        _pool.disconnect()
        _pool = None
    logger.info("Closed Redis connection pool")