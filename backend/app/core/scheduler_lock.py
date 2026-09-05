"""
Distributed Scheduler Lock
Prevents duplicate scheduler execution when running multiple app instances.

Uses Redis SET NX (atomic claim) with TTL for automatic expiry.
Single-process deployments work fine (lock is always acquired).
Multi-instance deployments get exactly one scheduler per lock window.
"""

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SchedulerLock:
    """Redis-backed distributed lock for scheduler singletons."""

    def __init__(self, lock_key: str = "leadstream:scheduler:lock", ttl_seconds: int = 30):
        """
        Args:
            lock_key: Redis key for the lock
            ttl_seconds: Lock auto-expires after this many seconds (safety net)
        """
        self.lock_key = lock_key
        self.ttl_seconds = ttl_seconds
        self._redis = None
        self._lock_value = None  # Unique value to prevent releasing someone else's lock

    def _get_redis(self):
        """Lazy-init Redis connection."""
        if self._redis is not None:
            return self._redis
        try:
            from app.core.redis_pool import get_redis_client
            self._redis = get_redis_client()
            return self._redis
        except Exception as e:
            logger.warning(f"Redis unavailable for scheduler lock: {e}")
            return None

    def acquire(self, identifier: str = "default") -> bool:
        """
        Try to acquire the lock.
        Returns True if lock acquired, False if another instance holds it.
        """
        import uuid
        redis = self._get_redis()
        if redis is None:
            # Redis unavailable — assume single instance, always acquire
            logger.warning("Redis unavailable — scheduler lock disabled (single instance assumed)")
            return True

        self._lock_value = f"{identifier}:{uuid.uuid4().hex[:8]}"
        try:
            acquired = redis.set(
                self.lock_key,
                self._lock_value,
                nx=True,  # Only set if Not eXists
                ex=self.ttl_seconds,  # Auto-expire
            )
            if acquired:
                logger.info(f"Scheduler lock acquired: {self._lock_value}")
            else:
                current = redis.get(self.lock_key)
                logger.info(f"Scheduler lock held by: {current}")
            return bool(acquired)
        except Exception as e:
            logger.exception(f"Redis lock acquire failed: {e}")
            return True  # Fail open — allow scheduler to run

    def release(self) -> bool:
        """
        Release the lock only if we own it (compare-and-delete).
        """
        redis = self._get_redis()
        if redis is None or self._lock_value is None:
            return True

        try:
            # Lua script for atomic compare-and-delete
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            released = redis.eval(lua_script, 1, self.lock_key, self._lock_value)
            if released:
                logger.info(f"Scheduler lock released: {self._lock_value}")
            self._lock_value = None
            return bool(released)
        except Exception as e:
            logger.exception(f"Redis lock release failed: {e}")
            return True

    def renew(self) -> bool:
        """Renew the lock TTL if we still own it."""
        redis = self._get_redis()
        if redis is None or self._lock_value is None:
            return True

        try:
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            renewed = redis.eval(
                lua_script, 1, self.lock_key,
                self._lock_value, self.ttl_seconds
            )
            return bool(renewed)
        except Exception as e:
            logger.warning(f"Lock renew failed: {e}")
            return False


# Singleton instances for different scheduler tasks
_followup_lock = SchedulerLock("leadstream:scheduler:followup", ttl_seconds=60)
_scheduled_lock = SchedulerLock("leadstream:scheduler:scheduled", ttl_seconds=60)
_autopilot_lock = SchedulerLock("leadstream:scheduler:autopilot", ttl_seconds=300)
_reply_poll_lock = SchedulerLock("leadstream:scheduler:reply_poll", ttl_seconds=600)
_reply_cleanup_lock = SchedulerLock("leadstream:scheduler:reply_cleanup", ttl_seconds=600)
_maintenance_lock = SchedulerLock("leadstream:scheduler:maintenance", ttl_seconds=3600)


@contextmanager
def scheduler_critical_section(lock: SchedulerLock, task_name: str):
    """
    Context manager for scheduler critical sections.
    Acquires lock, runs task, releases lock.
    If lock can't be acquired, skips the task silently.
    """
    if not lock.acquire(identifier=task_name):
        logger.debug(f"Skipping {task_name} — held by another instance")
        return
    try:
        yield
    finally:
        lock.release()
