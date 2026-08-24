"""
Worker Pool - Manages concurrent workers per user
"""

import threading
import time
import rq
from typing import Dict, Optional, List
from app.core.config import get_email_engine_settings
from app.email_engine.worker.rate_limiter import get_rate_limiter
import logging

logger = logging.getLogger(__name__)


class WorkerPool:
    """
    Manages worker processes for email sending.
    Limits concurrency per user and overall.
    """
    
    def __init__(self):
        settings = get_email_engine_settings()
        self.workers_per_user = settings.workers_per_user
        self.max_total_workers = settings.max_total_workers
        self.rate_limiter = get_rate_limiter()
        
        self._active_workers: Dict[int, int] = {}  # user_id -> count
        self._total_active = 0
        self._lock = threading.Lock()
        self._worker_threads: List[threading.Thread] = []
        self._running = False
    
    def can_start_worker(self, user_id: int) -> bool:
        """Check if we can start a worker for this user"""
        with self._lock:
            user_count = self._active_workers.get(user_id, 0)
            return user_count < self.workers_per_user and self._total_active < self.max_total_workers
    
    def acquire_slot(self, user_id: int) -> bool:
        """Acquire a worker slot for user"""
        with self._lock:
            if not self.can_start_worker(user_id):
                return False
            
            self._active_workers[user_id] = self._active_workers.get(user_id, 0) + 1
            self._total_active += 1
            return True
    
    def release_slot(self, user_id: int):
        """Release a worker slot"""
        with self._lock:
            if user_id in self._active_workers:
                self._active_workers[user_id] = max(0, self._active_workers[user_id] - 1)
                if self._active_workers[user_id] == 0:
                    del self._active_workers[user_id]
                self._total_active = max(0, self._total_active - 1)
    
    def get_stats(self) -> dict:
        """Get pool statistics"""
        with self._lock:
            return {
                'total_active': self._total_active,
                'max_total': self.max_total_workers,
                'per_user': dict(self._active_workers),
                'workers_per_user_limit': self.workers_per_user,
            }
    
    def start_worker(self, worker_func, user_id: int, *args, **kwargs) -> Optional[threading.Thread]:
        """Start a worker thread if slot available"""
        if not self.acquire_slot(user_id):
            return None
        
        def wrapped():
            try:
                worker_func(*args, **kwargs)
            finally:
                self.release_slot(user_id)
        
        thread = threading.Thread(target=wrapped, daemon=True)
        thread.start()
        
        with self._lock:
            self._worker_threads.append(thread)
        
        return thread


class Dispatcher:
    """
    Dispatches jobs from priority queues to worker pool.
    Respects priority ordering and rate limits.
    """
    
    def __init__(self, pool: WorkerPool):
        self.pool = pool
        self.rate_limiter = get_rate_limiter()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start dispatcher loop"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._thread.start()
        logger.info("Dispatcher started")
    
    def stop(self):
        """Stop dispatcher"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Dispatcher stopped")
    
    def _dispatch_loop(self):
        """Main dispatch loop - pulls from queues and assigns to workers"""
        from app.email_engine.queue.registry import get_priority_queue, get_scheduled_queue
        from app.email_engine.queue.job import EmailPriority
        
        while self._running:
            try:
                # Check queues in priority order
                job_dispatched = False
                
                for priority in [EmailPriority.HIGH, EmailPriority.NORMAL, EmailPriority.LOW]:
                    queue = get_priority_queue(priority)
                    
                    # Peek at next job
                    job_ids = queue.get_job_ids(0, 1)
                    if not job_ids:
                        continue
                    
                    job = queue.fetch_job(job_ids[0])
                    if not job:
                        continue
                    
                    job_data = job.meta.get('job_data', {})
                    user_id = job_data.get('user_id')
                    
                    if not user_id:
                        logger.warning(f"Job {job.id} missing user_id")
                        continue
                    
                    # Check rate limit
                    if not self.rate_limiter.try_acquire(user_id):
                        # Rate limited, try next priority or wait
                        continue
                    
                    # Check worker pool capacity
                    if not self.pool.can_start_worker(user_id):
                        continue
                    
                    # Got a job we can dispatch
                    logger.info(f"Dispatching job {job.id} for user {user_id} (priority={priority.name})")
                    
                    # Requeue for actual processing (separate from dispatch)
                    # The actual worker will pick it up
                    job_dispatched = True
                    break
                
                if not job_dispatched:
                    time.sleep(1)  # No jobs available, short sleep
                    
            except Exception as e:
                logger.error(f"Dispatch loop error: {e}")
                time.sleep(5)


# Singletons
_pool: Optional[WorkerPool] = None
_dispatcher: Optional[Dispatcher] = None


def get_worker_pool() -> WorkerPool:
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool


def get_dispatcher() -> Dispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher(get_worker_pool())
    return _dispatcher