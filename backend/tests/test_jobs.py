from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import Base, Job, make_sessions


@pytest.fixture
def job_db(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "worker-test-secret-not-for-production-1234")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/jobs.db")
    settings.cache_clear()
    from app import tasks

    monkeypatch.setattr(tasks, "cfg", settings())
    engine, sessions = make_sessions(settings().database_url)
    Base.metadata.create_all(engine)
    yield tasks, sessions
    engine.dispose()
    settings.cache_clear()


NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def add_running_job(sessions, job_id, started_ago_seconds, attempts):
    with sessions() as db:
        db.add(
            Job(
                id=job_id,
                kind="video",
                resource_id="v",
                status="running",
                attempts=attempts,
                started_at=NOW - timedelta(seconds=started_ago_seconds),
            )
        )
        db.commit()


def job(sessions, job_id):
    with sessions() as db:
        return db.get(Job, job_id)


def test_claim_sets_started_at_and_counts_attempts(job_db, monkeypatch):
    tasks, sessions = job_db
    from app import runtime

    monkeypatch.setattr(runtime, "execute", lambda kind, resource_id, progress: None)
    with sessions() as db:
        db.add(Job(id="a", kind="video", resource_id="v"))
        db.commit()
    tasks.run_job.run("a")
    row = job(sessions, "a")
    assert row.attempts == 1
    assert row.started_at is not None


def test_stale_running_job_is_requeued(job_db):
    tasks, sessions = job_db
    add_running_job(sessions, "stale", started_ago_seconds=1300, attempts=1)
    assert tasks.recover_stale_jobs(sessions, NOW) == ["stale"]
    row = job(sessions, "stale")
    assert row.status == "queued"
    assert row.started_at is None


def test_sweep_leaves_recent_running_jobs_alone(job_db):
    tasks, sessions = job_db
    add_running_job(sessions, "fresh", started_ago_seconds=100, attempts=1)
    assert tasks.recover_stale_jobs(sessions, NOW) == []
    assert job(sessions, "fresh").status == "running"


def test_poison_job_fails_after_max_attempts(job_db):
    tasks, sessions = job_db
    add_running_job(sessions, "poison", started_ago_seconds=1300, attempts=3)
    assert tasks.recover_stale_jobs(sessions, NOW) == []
    row = job(sessions, "poison")
    assert row.status == "failed"
    assert "worker" in row.error.lower()


def test_requeue_is_conditional(job_db):
    tasks, sessions = job_db
    add_running_job(sessions, "stale", started_ago_seconds=1300, attempts=1)
    first = tasks.recover_stale_jobs(sessions, NOW)
    second = tasks.recover_stale_jobs(sessions, NOW)
    assert first == ["stale"]
    assert second == []


def test_worker_claims_once_and_records_failure_without_exposing_details(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "worker-test-secret-not-for-production-1234")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/jobs.db")
    settings.cache_clear()
    from app import runtime, tasks

    monkeypatch.setattr(tasks, "cfg", settings())
    engine, sessions = make_sessions(settings().database_url)
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add_all([Job(id="good", kind="video", resource_id="v"), Job(id="bad", kind="video", resource_id="bad")])
        db.commit()
    calls = []

    def execute(kind, resource_id, progress):
        calls.append(resource_id)
        if resource_id == "bad":
            raise ValueError("internal-detail-not-for-http")
        progress(50)

    monkeypatch.setattr(runtime, "execute", execute)
    tasks.run_job.run("good")
    tasks.run_job.run("good")
    tasks.run_job.run("bad")
    with sessions() as db:
        rows = {row.id: row for row in db.scalars(select(Job))}
        assert rows["good"].status == "completed"
        assert rows["good"].progress == 100
        assert rows["bad"].status == "failed"
        assert "internal-detail" not in rows["bad"].error
    assert calls == ["v", "bad"]
    settings.cache_clear()
