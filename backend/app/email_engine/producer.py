"""
Email Producer - Public API for enqueueing emails
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from app.core.config import get_email_engine_settings
from app.email_engine.queue.connection import get_redis_client
from app.email_engine.queue.job import EmailJob, EmailPriority
from app.email_engine.queue.registry import enqueue_job, enqueue_scheduled

logger = logging.getLogger(__name__)


class EmailProducer:
    """High-level API for sending emails via queue"""

    def __init__(self):
        self.settings = get_email_engine_settings()

    def _generate_idempotency_key(self, lead_id: int | None = None,
                                   template_name: str | None = None,
                                   stage: int | None = None) -> str:
        """Generate unique idempotency key"""
        parts = ["email"]
        if lead_id:
            parts.append(f"lead{lead_id}")
        if template_name:
            parts.append(template_name.replace(" ", "_"))
        if stage:
            parts.append(f"stage{stage}")
        parts.append(uuid.uuid4().hex[:8])
        return "_".join(parts)

    def send_now(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        user_id: int,
        from_email: str | None = None,
        from_name: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        lead_id: int | None = None,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        template_name: str | None = None,
        tracking_enabled: bool = True,
        priority: EmailPriority = EmailPriority.HIGH,
        idempotency_key: str | None = None,
    ) -> str:
        """
        Enqueue immediate email send.
        Returns job ID (idempotency key).
        """
        if idempotency_key is None:
            idempotency_key = self._generate_idempotency_key(lead_id, template_name)

        job = EmailJob(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            user_id=user_id,
            from_email=from_email,
            from_name=from_name,
            cc=cc,
            bcc=bcc,
            lead_id=lead_id,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            attachments=attachments,
            template_name=template_name,
            tracking_enabled=tracking_enabled,
            priority=priority,
            idempotency_key=idempotency_key,
        )

        job_id = enqueue_job(job)
        logger.info(f"Enqueued immediate send: {job_id} to {to_email}")
        return job_id

    def send_scheduled(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        user_id: int,
        scheduled_at: datetime,
        from_email: str | None = None,
        from_name: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        lead_id: int | None = None,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        template_name: str | None = None,
        tracking_enabled: bool = True,
        priority: EmailPriority = EmailPriority.NORMAL,
        idempotency_key: str | None = None,
    ) -> str:
        """
        Enqueue email for future delivery.
        Returns job ID.
        """
        if idempotency_key is None:
            idempotency_key = self._generate_idempotency_key(lead_id, template_name)

        job = EmailJob(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            user_id=user_id,
            from_email=from_email,
            from_name=from_name,
            cc=cc,
            bcc=bcc,
            lead_id=lead_id,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            attachments=attachments,
            template_name=template_name,
            tracking_enabled=tracking_enabled,
            priority=priority,
            idempotency_key=idempotency_key,
            scheduled_at=scheduled_at,
        )

        job_id = enqueue_scheduled(job, scheduled_at)
        logger.info(f"Enqueued scheduled send: {job_id} for {scheduled_at}")
        return job_id

    def send_followup(
        self,
        lead_id: int,
        stage: int,
        user_id: int,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: str | None = None,
        from_name: str | None = None,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
        template_name: str | None = None,
        priority: EmailPriority = EmailPriority.NORMAL,
    ) -> str:
        """
        Enqueue follow-up email.
        Generates idempotency key from lead_id + stage.
        """
        try:
            idempotency_key = f"followup_lead{lead_id}_stage{stage}"

            job = EmailJob(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                user_id=user_id,
                from_email=from_email,
                from_name=from_name,
                lead_id=lead_id,
                thread_id=thread_id,
                in_reply_to=in_reply_to,
                template_name=template_name,
                priority=priority,
                idempotency_key=idempotency_key,
            )

            job_id = enqueue_job(job)
            logger.info(f"Enqueued followup: {job_id} for lead {lead_id} stage {stage}")
            return job_id
        except Exception as e:
            logger.exception(f"Failed to enqueue followup for lead {lead_id}: {e}")
            raise

    def send_bulk(self, jobs: list[EmailJob]) -> list[str]:
        """
        Batch enqueue multiple jobs efficiently using pipeline.
        Returns list of job IDs.
        """
        redis = get_redis_client()
        redis.pipeline()

        job_ids = []
        for job in jobs:
            if job.idempotency_key is None:
                job.idempotency_key = self._generate_idempotency_key(
                    job.lead_id, job.template_name
                )

            # Use RQ's enqueue directly for bulk
            from app.email_engine.queue.registry import get_priority_queue
            queue = get_priority_queue(job.priority)

            rq_job = queue.enqueue(
                'app.email_engine.worker.sender.send_email_job',
                job.to_dict(),
                job_id=job.idempotency_key,
                meta={'job_data': job.to_dict()},
            )
            job_ids.append(rq_job.id)

        logger.info(f"Enqueued {len(job_ids)} bulk jobs")
        return job_ids

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get job status by ID"""
        from app.email_engine.queue.registry import (
            get_dead_letter_queue,
            get_queue,
            get_scheduled_queue,
        )

        # Check all queues
        for queue in [get_queue(), get_scheduled_queue(), get_dead_letter_queue()]:
            job = queue.fetch_job(job_id)
            if job:
                return {
                    'id': job.id,
                    'status': job.get_status(),
                    'result': job.result,
                    'created_at': job.created_at.isoformat() if job.created_at else None,
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'ended_at': job.ended_at.isoformat() if job.ended_at else None,
                    'exc_info': job.exc_info,
                }
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job"""
        from app.email_engine.queue.registry import get_queue, get_scheduled_queue

        for queue in [get_queue(), get_scheduled_queue()]:
            job = queue.fetch_job(job_id)
            if job and job.get_status() in ['queued', 'scheduled']:
                job.cancel()
                logger.info(f"Cancelled job {job_id}")
                return True
        return False


# Singleton
_producer: EmailProducer | None = None


def get_email_producer() -> EmailProducer:
    global _producer
    if _producer is None:
        _producer = EmailProducer()
    return _producer
