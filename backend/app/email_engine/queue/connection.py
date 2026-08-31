"""
Redis Connection Pool for Email Engine

Delegates to the shared pool in app.core.redis_pool to avoid creating
a second connection pool that would exhaust Redis maxclients on
low-tier plans (e.g. Render free).
"""

import logging

import redis

from app.core.redis_pool import get_redis_pool

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get Redis client from the shared pool"""
    global _client
    if _client is None:
        _client = redis.Redis(connection_pool=get_redis_pool())
    return _client


def close_redis_pool():
    """Close connection (for graceful shutdown)"""
    global _client
    if _client:
        _client.close()
        _client = None
    logger.info("Closed Redis client")
