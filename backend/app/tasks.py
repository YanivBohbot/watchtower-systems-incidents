"""SQL-backed outbox + atomic claim: queue delivery may happen more than once."""

import logging

from celery import Celery
from sqlalchemy import select, update

from app.config import settings
from app.db import Job, make_sessions

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


@celery.task(name="watchtower.run", soft_time_limit=900, time_limit=960)
def run_job(job_id):
    from app.runtime import execute

    engine, sessions = make_sessions(cfg.database_url)
    try:
        with sessions() as db:
            claimed = db.execute(
                update(Job).where(Job.id == job_id, Job.status == "queued").values(status="running", error=None)
            )
            db.commit()
            if claimed.rowcount != 1:
                return
            job = db.get(Job, job_id)
            kind, resource_id = job.kind, job.resource_id

        def progress(percent):
            with sessions() as db:
                db.execute(update(Job).where(Job.id == job_id).values(progress=percent))
                db.commit()

        try:
            execute(kind, resource_id, progress)
        except Exception as error:
            log.exception("Job failed: id=%s kind=%s", job_id, kind)
            with sessions() as db:
                db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(status="failed", error=f"{type(error).__name__}: check the worker logs.")
                )
                db.commit()
        else:
            with sessions() as db:
                db.execute(update(Job).where(Job.id == job_id).values(status="completed", progress=100))
                db.commit()
    finally:
        engine.dispose()


@celery.task(name="watchtower.sweep")
def sweep():
    engine, sessions = make_sessions(cfg.database_url)
    try:
        with sessions() as db:
            jobs = list(db.scalars(select(Job).where(Job.status == "queued").limit(100)))
        for job in jobs:
            queue = "investigation" if job.kind in ("investigate", "review") else "processing"
            run_job.apply_async(args=[job.id], queue=queue)
    finally:
        engine.dispose()
