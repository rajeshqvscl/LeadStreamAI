"""
Standalone RQ worker for the email engine.

Consumes emails_high / emails_normal / emails_low and runs
app.email_engine.worker.sender.send_email_job for each job.

Why this exists:
  The FastAPI process runs an in-process Dispatcher (see
  app/email_engine/worker/pool.py) that also consumes these queues, but a
  dedicated worker service is the production-grade consumer — it pops jobs
  atomically (no lost/duplicate head), respects per-job timeouts, and keeps
  email sending out of the API process entirely.

Run locally (uses app/.env credentials — only if you intend to work on the
same Redis/DB the app uses):
    python worker.py

Run in production (env vars supplied by the platform, e.g. Render):
    python worker.py
"""

import os

from dotenv import load_dotenv

# Load app/.env for local runs, but never override real env vars
# (load_dotenv does not override by default).
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

import logging

from rq import Queue, Worker

from app.email_engine.queue.connection import get_redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("leadstream.worker")

# Delay importing app modules that trigger side effects until the logger is up.
QUEUE_NAMES = ["emails_high", "emails_normal", "emails_low"]


def main() -> None:
    redis_conn = get_redis_client()
    queues = [Queue(name, connection=redis_conn) for name in QUEUE_NAMES]
    logger.info("Starting RQ worker on queues: %s", QUEUE_NAMES)

    worker = Worker(
        queues,
        connection=redis_conn,
        name="leadstream-worker",
        default_worker_ttl=420,   # heartbeat
        disable_default_exception_handler=False,
    )
    worker.work(logging_level=logging.INFO)


if __name__ == "__main__":
    main()
