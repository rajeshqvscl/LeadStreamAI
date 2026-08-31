"""
Redis-backed Rate Limiter for multi-instance deployments.
Uses sliding window log algorithm with Redis sorted sets.
"""
import time
import redis.asyncio as redis
from typing import Optional
import logging
from functools import wraps
from fastapi import Request, HTTPException, Depends

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.
    
    Algorithm:
    - Store request timestamps in a sorted set (score = timestamp)
    - Remove expired entries (older than window)
    - Count remaining entries
    - If count >= limit, reject request
    - Otherwise, add current timestamp and allow
    """
    
    def __init__(
        self,
        redis_url: str,
        default_limit: int = 100,
        default_window: int = 60,
        max_connections: int = 5,
    ):
        pool = redis.ConnectionPool.from_url(
            redis_url,
            decode_responses=True,
            max_connections=max_connections,
        )
        self.redis = redis.Redis(connection_pool=pool)
        self.default_limit = default_limit
        self.default_window = default_window
    
    async def check_limit(
        self,
        key: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.
        
        Returns:
            (allowed: bool, info: dict)
            info contains: current, limit, reset_at, retry_after
        """
        limit = limit or self.default_limit
        window = window or self.default_window
        now = time.time()
        window_start = now - window
        
        try:
            pipe = self.redis.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request (optimistically)
            pipe.zadd(key, {f"{now}:{id(key)}": now})
            
            # Set expiry on the key
            pipe.expire(key, window + 1)
            
            results = await pipe.execute()
            current_count = results[1]
            
            # If we exceeded limit, remove the optimistic add
            if current_count >= limit:
                await self.redis.zrem(key, f"{now}:{id(key)}")
                return False, {
                    "allowed": False,
                    "current": current_count,
                    "limit": limit,
                    "reset_at": int(now + window),
                    "retry_after": window,
                }
            
            return True, {
                "allowed": True,
                "current": current_count + 1,
                "limit": limit,
                "reset_at": int(now + window),
                "retry_after": 0,
            }
            
        except redis.RedisError as e:
            logger.error(f"Redis rate limiter error: {e}")
            # Fail open - allow request if Redis is down
            return True, {
                "allowed": True,
                "current": 0,
                "limit": limit,
                "reset_at": int(now + window),
                "retry_after": 0,
                "warning": "Rate limiter unavailable - failing open",
            }
    
    async def close(self):
        """Close Redis connection."""
        await self.redis.close()


# Global rate limiter instance
_rate_limiter: Optional[SlidingWindowRateLimiter] = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        import os
        redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
        _rate_limiter = SlidingWindowRateLimiter(redis_url, max_connections=2)
    return _rate_limiter


# FastAPI dependency for rate limiting
async def rate_limit_dependency(
    request: Request,
    limit: int = 100,
    window: int = 60,
) -> dict:
    """
    FastAPI dependency that enforces rate limiting.
    
    Usage:
        @app.get("/api/endpoint")
        async def my_endpoint(rate_info: dict = Depends(rate_limit_dependency)):
            ...
    """
    limiter = get_rate_limiter()
    
    # Create key from user ID + endpoint
    user_id = getattr(request.state, "user_id", None) or request.client.host
    endpoint = request.url.path
    key = f"ratelimit:{user_id}:{endpoint}"
    
    allowed, info = await limiter.check_limit(key, limit, window)
    
    # Add rate limit headers
    request.state.rate_limit_info = info
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": info["retry_after"],
                "limit": info["limit"],
            },
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info["reset_at"]),
                "Retry-After": str(info["retry_after"]),
            },
        )
    
    return info


# Middleware for global rate limiting
class RateLimitMiddleware:
    """Global rate limiting middleware."""
    
    def __init__(self, app, limiter: SlidingWindowRateLimiter, default_limit: int = 100, default_window: int = 60):
        self.app = app
        self.limiter = limiter
        self.default_limit = default_limit
        self.default_window = default_window
    
    # Paths that should skip rate limiting (health checks, readiness probes)
    _SKIP_PATHS = frozenset({"/", "/healthz", "/health", "/health/ready", "/health/alive", "/api/v1/health"})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip rate limiting for health check endpoints
        path = scope.get("path", "/")
        if path in self._SKIP_PATHS:
            await self.app(scope, receive, send)
            return
        
        # Extract client identifier
        client_host = scope.get("client", ("unknown", 0))[0]
        key = f"ratelimit:global:{client_host}:{path}"
        
        # Check rate limit
        allowed, info = await self.limiter.check_limit(
            key, self.default_limit, self.default_window
        )
        
        if not allowed:
            # Send 429 response
            response_body = b'{"error": "Rate limit exceeded", "retry_after": ' + str(info["retry_after"]).encode() + b'}'
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"x-ratelimit-limit", str(info["limit"]).encode()),
                    (b"x-ratelimit-remaining", b"0"),
                    (b"x-ratelimit-reset", str(info["reset_at"]).encode()),
                    (b"retry-after", str(info["retry_after"]).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": response_body,
            })
            return
        
        # Add rate limit info to scope for downstream use
        scope["rate_limit_info"] = info
        await self.app(scope, receive, send)