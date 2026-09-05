"""
Queue Registry and Priority Management
"""

import logging
from datetime import datetime

import rq

from app.core.config import get_email_engine_settings
from app.email_engine.queue.connection import get_redis_client
from app.email_engine.queue.job import EmailPriority

logger = logging.getLogger(__name__)

# Queue instances (created lazily)
_queues: dict = {}


def get_queue(name: str | None = None) -> rq.Queue:
    """Get or create RQ queue by name"""
    settings = get_email_engine_settings()
    queue_name = name or settings.queue_name

    if queue_name not in _queues:
        _queues[queue_name] = rq.Queue(
            queue_name,
            connection=get_redis_client(),
            default_timeout=300,  # 5 min job timeout
        )
        logger.info(f"Created queue: {queue_name}")

    return _queues[queue_name]


def get_scheduled_queue() -> rq.Queue:
    """Get scheduled emails queue"""
    settings = get_email_engine_settings()
    if settings.scheduled_queue_name not in _queues:
        _queues[settings.scheduled_queue_name] = rq.Queue(
            settings.scheduled_queue_name,
            connection=get_redis_client(),
            default_timeout=300,
        )
    return _queues[settings.scheduled_queue_name]


def get_dead_letter_queue() -> rq.Queue:
    """Get dead letter queue for failed jobs"""
    settings = get_email_engine_settings()
    if settings.dead_letter_queue_name not in _queues:
        _queues[settings.dead_letter_queue_name] = rq.Queue(
            settings.dead_letter_queue_name,
            connection=get_redis_client(),
            default_timeout=300,
        )
    return _queues[settings.dead_letter_queue_name]


def get_priority_queue(priority: EmailPriority) -> rq.Queue:
    """Get priority queue (HIGH/NORMAL/LOW)"""
    priority_names = {
        EmailPriority.HIGH: "emails_high",
        EmailPriority.NORMAL: "emails_normal",
        EmailPriority.LOW: "emails_low",
    }
    name = priority_names.get(priority, "emails_normal")
    return get_queue(name)


def enqueue_job(job, queue: rq.Queue | None = None) -> str:
    """Enqueue a job and return job ID"""

    if queue is None:
        queue = get_priority_queue(job.priority)

    # Use RQ's built-in job ID generation
    rq_job = queue.enqueue(
        'app.email_engine.worker.sender.send_email_job',
        job.to_dict(),
        job_id=job.idempotency_key,
        meta={'job_data': job.to_dict()},
    )
    return rq_job.id


def enqueue_scheduled(job, scheduled_at: datetime) -> str:
    """Enqueue job for future execution"""

    queue = get_scheduled_queue()
    delay = (scheduled_at - datetime.utcnow()).total_seconds()

    if delay <= 0:
        # Already due, enqueue immediately
        return enqueue_job(job)

    rq_job = queue.enqueue_in(
        delay,
        'app.email_engine.worker.sender.send_email_job',
        job.to_dict(),
        job_id=job.idempotency_key,
        meta={'job_data': job.to_dict()},
    )
    return rq_job.id


def get_queue_stats() -> dict:
    """Get stats for all queues"""
    stats = {}
    for name, queue in _queues.items():
        stats[name] = {
            'pending': len(queue),
            'started': queue.started_job_registry.count,
            'finished': queue.finished_job_registry.count,
            'failed': queue.failed_job_registry.count,
        }
    return stats


def cancel_pending_jobs_for_leads(lead_ids) -> int:
    """
    Delete queued/scheduled email jobs that target any of the given leads.

    Called whenever a lead replies (or is manually marked responded / stopped)
    so its scheduled & pending follow-up emails are deleted instead of sitting
    in the queue until a worker pops them.

    Job ids embed the lead id as ``lead<id>_`` (e.g. ``followup_lead123_stage2``,
    ``email_lead123_...``), so matching is done on the queue's id list without
    deserializing payloads. Removal uses ``Queue.remove`` for jobs waiting in
    the queue list and ``job.cancel()`` for delayed (not-yet-due) jobs.

    Returns the number of jobs removed.
    """
    if not lead_ids:
        return 0

    from app.email_engine.queue.job import EmailPriority

    targets = [f"lead{int(lid)}_" for lid in lead_ids if lid]
    if not targets:
        return 0

    removed = 0
    queues = [
        get_priority_queue(EmailPriority.HIGH),
        get_priority_queue(EmailPriority.NORMAL),
        get_priority_queue(EmailPriority.LOW),
        get_scheduled_queue(),
    ]

    for queue in queues:
        try:
            job_ids = queue.get_job_ids()
        except Exception as e:
            logger.warning(f"cancel_pending_jobs: could not list {queue.name}: {e}")
            continue

        for job_id in job_ids or []:
            if not any(t in job_id for t in targets):
                continue
            try:
                queue.remove(job_id)
                removed += 1
            except Exception as e:
                logger.warning(f"cancel_pending_jobs: failed to remove {job_id} from {queue.name}: {e}")

    # Delayed (not-yet-due) jobs live in the scheduled registry until due.
    try:
        scheduled_ids = get_scheduled_queue().scheduled_job_registry.get_job_ids()
        for job_id in scheduled_ids or []:
            if not any(t in job_id for t in targets):
                continue
            try:
                job = get_scheduled_queue().fetch_job(job_id)
                if job is not None:
                    job.cancel()
                    removed += 1
            except Exception as e:
                logger.warning(f"cancel_pending_jobs: failed to cancel scheduled {job_id}: {e}")
    except Exception as e:
        logger.warning(f"cancel_pending_jobs: scheduled-registry scan failed: {e}")

    if removed:
        logger.info("Cancelled %d pending email job(s) for leads %s", removed, [int(l) for l in lead_ids if l])
    return removed
