"""
Shared Redis connection pool for the sync (blocking) Redis clients used across
the app. Routing every module-level client through this single pool keeps the
total number of connections bounded, which matters on Redis plans with a low
`maxclients` limit (e.g. the free tier).
"""
import os

import redis

_POOL: "redis.ConnectionPool | None" = None


def get_redis_pool() -> "redis.ConnectionPool":
    global _POOL
    if _POOL is None:
        url = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
        _POOL = redis.ConnectionPool.from_url(
            url,
            decode_responses=True,
            max_connections=10,
        )
    return _POOL


def get_redis_client() -> "redis.Redis":
    return redis.Redis(connection_pool=get_redis_pool())
