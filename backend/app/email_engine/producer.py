"""
Email Producer - Public API for enqueueing emails
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.email_engine.queue.job import EmailJob, EmailPriority
from app.email_engine.queue.registry import enqueue_job, enqueue_scheduled
from app.email_engine.queue.connection import get_redis_client
from app.core.config import get_email_engine_settings
import logging

logger = logging.getLogger(__name__)


class EmailProducer:
    """High-level API for sending emails via queue"""
    
    def __init__(self):
        self.settings = get_email_engine_settings()
    
    def _generate_idempotency_key(self, lead_id: Optional[int] = None, 
                                   template_name: Optional[str] = None,
                                   stage: Optional[int] = None) -> str:
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
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        lead_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        template_name: Optional[str] = None,
        tracking_enabled: bool = True,
        priority: EmailPriority = EmailPriority.HIGH,
        idempotency_key: Optional[str] = None,
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
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        lead_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        template_name: Optional[str] = None,
        tracking_enabled: bool = True,
        priority: EmailPriority = EmailPriority.NORMAL,
        idempotency_key: Optional[str] = None,
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
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        template_name: Optional[str] = None,
        priority: EmailPriority = EmailPriority.NORMAL,
    ) -> str:
        """
        Enqueue follow-up email.
        Generates idempotency key from lead_id + stage.
        """
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
    
    def send_bulk(self, jobs: List[EmailJob]) -> List[str]:
        """
        Batch enqueue multiple jobs efficiently using pipeline.
        Returns list of job IDs.
        """
        redis = get_redis_client()
        pipe = redis.pipeline()
        
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
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status by ID"""
        from app.email_engine.queue.registry import get_queue, get_scheduled_queue, get_dead_letter_queue
        
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
_producer: Optional[EmailProducer] = None


def get_email_producer() -> EmailProducer:
    global _producer
    if _producer is None:
        _producer = EmailProducer()
    return _producer