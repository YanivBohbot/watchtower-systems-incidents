from sqlalchemy import select

from app.config import settings
from app.db import Base, Job, make_sessions


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
