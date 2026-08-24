"""
Queue Registry and Priority Management
"""

import rq
from datetime import datetime
from typing import Optional
from app.email_engine.queue.connection import get_redis_client
from app.email_engine.queue.job import EmailPriority
from app.core.config import get_email_engine_settings
import logging

logger = logging.getLogger(__name__)

# Queue instances (created lazily)
_queues: dict = {}


def get_queue(name: Optional[str] = None) -> rq.Queue:
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


def enqueue_job(job, queue: Optional[rq.Queue] = None) -> str:
    """Enqueue a job and return job ID"""
    from app.email_engine.queue.job import EmailJob
    
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
    from app.email_engine.queue.job import EmailJob
    
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