from .observability import (
    export_all_metrics,
    get_structured_logger,
    setup_structured_logging,
)
from .producer import EmailProducer, get_email_producer
from .queue import (
    EmailJob,
    EmailPriority,
    enqueue_job,
    enqueue_scheduled,
    get_dead_letter_queue,
    get_queue,
    get_scheduled_queue,
)
from .template import TemplateEngine, get_template_engine, render_email
from .worker import (
    Dispatcher,
    WorkerPool,
    get_dispatcher,
    get_rate_limiter,
    get_worker_pool,
    send_email_direct,
    send_email_job,
)

__all__ = [
    "EmailProducer",
    "get_email_producer",
    "EmailJob",
    "EmailPriority",
    "get_queue",
    "get_scheduled_queue",
    "get_dead_letter_queue",
    "enqueue_job",
    "enqueue_scheduled",
    "TemplateEngine",
    "get_template_engine",
    "render_email",
    "get_rate_limiter",
    "send_email_job",
    "send_email_direct",
    "get_worker_pool",
    "get_dispatcher",
    "WorkerPool",
    "Dispatcher",
    "setup_structured_logging",
    "get_structured_logger",
    "export_all_metrics",
]

# Version
__version__ = "1.0.0"
