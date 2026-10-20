"""SQL-backed outbox + atomic claim: queue delivery may happen more than once."""

import logging
from datetime import datetime, timedelta, timezone

from celery import Celery
from sqlalchemy import select, update

from app.core.config import settings
from app.database.models import Job, now
from app.database.session import make_sessions

# A live worker cannot hold a job past run_job's hard time_limit (960 s), so a job
# still "running" after this lease belongs to a worker that died.
JOB_LEASE_SECONDS = 1200
MAX_JOB_ATTEMPTS = 3

cfg = settings()
celery = Celery("watchtower", broker=cfg.redis_url)
celery.conf.update(
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "dispatch-sql-outbox": {"task": "watchtower.sweep", "schedule": 30.0, "options": {"queue": "processing"}}
    },
)
log = logging.getLogger(__name__)


def queue_for_kind(kind: str) -> str:
    """LLM jobs get their own queue so a long investigation never delays video or document processing."""
    return "investigation" if kind in ("investigate", "review") else "processing"


@celery.task(name="watchtower.run", soft_time_limit=900, time_limit=960)
def run_job(job_id):
    from app.workers.job_handlers import execute

    engine, sessions = make_sessions(cfg.database_url)
    try:
        claimed_at = now()
        with sessions() as db:
            claimed = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "queued")
                .values(status="running", error=None, started_at=claimed_at, attempts=Job.attempts + 1)
            )
            db.commit()
            if claimed.rowcount != 1:
                return
            job = db.get(Job, job_id)
            kind, resource_id = job.kind, job.resource_id
        # Writes only apply while this claim still owns the row: once the sweep has
        # requeued the job and another worker claimed it, a late worker changes nothing.
        owned = (Job.id == job_id, Job.status == "running", Job.started_at == claimed_at)

        def progress(percent):
            with sessions() as db:
                db.execute(update(Job).where(*owned).values(progress=percent))
                db.commit()

        try:
            execute(kind, resource_id, progress)
        except Exception as error:
            log.exception("Job failed: id=%s kind=%s", job_id, kind)
            with sessions() as db:
                db.execute(
                    update(Job)
                    .where(*owned)
                    .values(status="failed", error=f"{type(error).__name__}: check the worker logs.")
                )
                db.commit()
        else:
            with sessions() as db:
                db.execute(update(Job).where(*owned).values(status="completed", progress=100))
                db.commit()
    finally:
        engine.dispose()


def recover_stale_jobs(sessions, current: datetime) -> list[str]:
    """Requeue jobs whose worker died; fail those that keep killing workers."""
    cutoff = current - timedelta(seconds=JOB_LEASE_SECONDS)
    requeued = []
    with sessions() as db:
        stale = list(db.scalars(select(Job).where(Job.status == "running", Job.started_at.is_not(None))))
        for job in stale:
            started = job.started_at if job.started_at.tzinfo else job.started_at.replace(tzinfo=timezone.utc)
            if started >= cutoff:
                continue
            values = (
                {"status": "failed", "error": "Worker stopped repeatedly; check the worker logs."}
                if job.attempts >= MAX_JOB_ATTEMPTS
                else {"status": "queued", "started_at": None}
            )
            # Repeat the observed state so a concurrent claim or recovery wins and this one is skipped.
            changed = db.execute(
                update(Job)
                .where(Job.id == job.id, Job.status == "running", Job.started_at == job.started_at)
                .values(**values)
            )
            if changed.rowcount == 1 and values["status"] == "queued":
                requeued.append(job.id)
        db.commit()
    return requeued


@celery.task(name="watchtower.sweep")
def sweep():
    engine, sessions = make_sessions(cfg.database_url)
    try:
        for job_id in recover_stale_jobs(sessions, now()):
            log.warning("Requeued job left running by a stopped worker: %s", job_id)
        with sessions() as db:
            jobs = list(db.scalars(select(Job).where(Job.status == "queued").limit(100)))
        for job in jobs:
            run_job.apply_async(args=[job.id], queue=queue_for_kind(job.kind))
    finally:
        engine.dispose()
