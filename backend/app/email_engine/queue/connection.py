"""
Redis Connection Pool for Email Engine

Uses its own connection pool with decode_responses=False because rq
serializes jobs as binary (pickle + zlib). The shared API pool has
decode_responses=True which would corrupt binary payloads.
"""

import logging
import os

import redis

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None
_client: redis.Redis | None = None


def get_redis_pool() -> redis.ConnectionPool:
    """Get or create Redis connection pool for email engine.

    decode_responses=False is critical — rq stores pickled + zlib
    compressed job data that must be returned as raw bytes.
    """
    global _pool
    if _pool is None:
        url = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
        _pool = redis.ConnectionPool.from_url(
            url,
            max_connections=4,
            # Without timeouts a hung Redis connection blocks the dispatcher
            # thread forever (seen in prod: queue stopped draining, job
            # backlog grew to ~8.8k). Fail fast and let the loop retry.
            socket_connect_timeout=5,
            socket_timeout=10,
            retry_on_timeout=False,
            # decode_responses defaults to False — that's what we need
        )
    return _pool


def get_redis_client() -> redis.Redis:
    """Get Redis client from email engine pool"""
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
    logger.info("Closed email engine Redis pool")
