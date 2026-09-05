"""
Worker Pool - Manages concurrent workers per user
"""

import logging
import threading
import time

from app.core.config import get_email_engine_settings
from app.email_engine.worker.rate_limiter import get_rate_limiter

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

        self._active_workers: dict[int, int] = {}  # user_id -> count
        self._total_active = 0
        self._lock = threading.Lock()
        self._worker_threads: list[threading.Thread] = []
        self._running = False

    def _can_start_worker_unlocked(self, user_id: int) -> bool:
        """Check worker-slot availability. Caller MUST hold self._lock.

        Never call this while holding the lock via can_start_worker() —
        threading.Lock is not reentrant and the nested acquire deadlocks.
        """
        user_count = self._active_workers.get(user_id, 0)
        return user_count < self.workers_per_user and self._total_active < self.max_total_workers

    def can_start_worker(self, user_id: int) -> bool:
        """Check if we can start a worker for this user"""
        with self._lock:
            return self._can_start_worker_unlocked(user_id)

    def acquire_slot(self, user_id: int) -> bool:
        """Acquire a worker slot for user"""
        with self._lock:
            if not self._can_start_worker_unlocked(user_id):
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

    def start_worker(self, worker_func, user_id: int, *args, **kwargs) -> threading.Thread | None:
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
        self._thread: threading.Thread | None = None
        self.last_iteration_ts: float | None = None
        self.last_iteration_queue: str | None = None

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
        """Main dispatch loop - pulls from queues and assigns to workers.

        FIX: the loop used to read the head job without ever removing it from
        the queue, so the queue never advanced (head starved every job behind
        it and the backlog only grew). Now the job is popped right before it is
        handed to a worker thread. Duplicate dispatch is prevented by the
        sender's atomic idempotency claim, so popping early is safe.
        """
        from app.email_engine.queue.job import EmailPriority
        from app.email_engine.queue.registry import get_priority_queue

        while self._running:
            try:
                job_dispatched = False

                for priority in [EmailPriority.HIGH, EmailPriority.NORMAL, EmailPriority.LOW]:
                    queue = get_priority_queue(priority)

                    try:
                        job_ids = queue.get_job_ids(0, 1)
                    except Exception as read_err:
                        logger.warning(f"Queue {queue.name} read failed: {read_err}")
                        self._record_iteration(queue.name)
                        self._record_error("queue_read")
                        continue
                    if not job_ids:
                        self._record_iteration(queue.name)
                        continue
                    self._record_iteration(queue.name)

                    job_id = job_ids[0]

                    try:
                        job = queue.fetch_job(job_id)
                    except Exception as fetch_err:
                        # Corrupt job object — drop the entry so the queue advances.
                        logger.warning(f"Failed to fetch job {job_id} (stale/corrupt?): {fetch_err} — removing")
                        self._pop_job(queue, job_id, outcome="corrupt")
                        job_dispatched = True
                        break

                    if not job:
                        # Ghost entry (job hash already expired) — drop it.
                        logger.warning(f"Job {job_id} has no object — removing stale queue entry")
                        self._pop_job(queue, job_id, outcome="ghost")
                        job_dispatched = True
                        break

                    job_data = job.meta.get('job_data', {}) or {}
                    user_id = job_data.get('user_id')

                    if not user_id:
                        # No owner to attribute the send to — park in DLQ, advance.
                        logger.warning(f"Job {job.id} missing user_id — moving to dead-letter queue")
                        self._park_in_dlq(queue, job_id)
                        self._pop_job(queue, job_id, outcome="no_user")
                        job_dispatched = True
                        break

                    if not self.rate_limiter.try_acquire(user_id):
                        continue

                    if not self.pool.can_start_worker(user_id):
                        continue

                    logger.info(f"Dispatching job {job.id} for user {user_id} (priority={priority.name})")

                    # Pop BEFORE handing to the worker so the head advances even
                    # if this job takes a while or fails.
                    self._pop_job(queue, job_id, outcome="dispatched")

                    thread = self.pool.start_worker(
                        self._run_job, user_id, job_id, job_data
                    )
                    if thread:
                        job_dispatched = True
                    else:
                        # Slot vanished between check and start — re-enqueue so
                        # the job is not lost.
                        try:
                            queue.enqueue_job(job)
                        except Exception as e:
                            logger.error(f"Could not re-enqueue {job_id} after pop: {e}")
                        job_dispatched = True
                    break

                if not job_dispatched:
                    time.sleep(1)

            except Exception as e:
                logger.exception(f"Dispatch loop error: {e}")
                self._record_error("loop")
                time.sleep(5)

    @staticmethod
    def _record_iteration(queue_name: str):
        try:
            from app.core.observability.metrics import EMAIL_DISPATCHER_ITERATIONS
            EMAIL_DISPATCHER_ITERATIONS.labels(priority=queue_name).inc()
        except Exception:
            pass
        try:
            dispatcher = get_dispatcher()
            dispatcher.last_iteration_ts = time.time()
            dispatcher.last_iteration_queue = queue_name
        except Exception:
            pass

    @staticmethod
    def _record_error(error: str):
        try:
            from app.core.observability.metrics import EMAIL_DISPATCHER_ERRORS
            EMAIL_DISPATCHER_ERRORS.labels(error=error).inc()
        except Exception:
            pass

    def _pop_job(self, queue, job_id: str, outcome: str = "dispatched"):
        """Remove a job id from the queue list so the head advances."""
        try:
            queue.remove(job_id)
            try:
                from app.core.observability.metrics import EMAIL_DISPATCHER_POPS
                EMAIL_DISPATCHER_POPS.labels(priority=queue.name, outcome=outcome).inc()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id} from {queue.name}: {e}")

    def _park_in_dlq(self, queue, job_id: str):
        """Move an undeliverable job to the dead-letter queue."""
        try:
            from app.email_engine.queue.registry import get_dead_letter_queue
            job = queue.fetch_job(job_id)
            if job is not None:
                dlq = get_dead_letter_queue()
                dlq.enqueue_job(job)
        except Exception as e:
            logger.warning(f"Failed to park {job_id} in DLQ: {e}")

    def _run_job(self, job_id: str, job_data: dict):
        """Worker thread target — runs the send and logs the outcome."""
        from app.email_engine.worker.sender import send_email_job
        try:
            result = send_email_job(job_data) or {}
            if not result.get('success'):
                reason = (
                    result.get('error')
                    or result.get('ownership_rejected')
                    or result.get('duplicate')
                    or 'retries exhausted'
                )
                logger.warning(f"Job {job_id} not sent: {reason}")
        except Exception as e:
            logger.exception(f"Job {job_id} raised: {e}")


# Singletons
_pool: WorkerPool | None = None
_dispatcher: Dispatcher | None = None
_dispatcher_start_error: str | None = None
_dispatcher_start_called: bool = False
POOL_MODULE_VERSION = "pool-v3"  # bumped with dispatcher diagnostics


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


def start_dispatcher() -> bool:
    """Start the email dispatcher, recording any failure for diagnostics.

    The lifespan previously called get_dispatcher().start() inside a bare
    try/except that only logged a warning — when construction raised (e.g. a
    transient Redis/DB hiccup at startup) the singleton stayed unset, the app
    kept running, and the email queue silently stopped draining. Here the error
    is remembered so /health/ready can surface it instead of guessing.
    """
    global _dispatcher_start_error, _dispatcher_start_called
    _dispatcher_start_called = True
    try:
        dispatcher = get_dispatcher()
        dispatcher.start()
        _dispatcher_start_error = None
        return True
    except Exception as e:
        _dispatcher_start_error = f"{type(e).__name__}: {e}"
        logger.warning(f"Could not start email dispatcher: {_dispatcher_start_error}")
        return False


def get_dispatcher_start_error() -> str | None:
    return _dispatcher_start_error


def dispatcher_start_called() -> bool:
    return _dispatcher_start_called
