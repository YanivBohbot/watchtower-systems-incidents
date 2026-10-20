"""Background jobs: list the latest ones and retry a failed one."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update

from app.api.dependencies import JobDispatcher, current_user, get_dispatcher, get_sessions, require_operator
from app.api.schemas import public
from app.database.models import Job

router = APIRouter()


@router.get("/api/jobs", dependencies=[Depends(current_user)])
def list_jobs(sessions=Depends(get_sessions)):
    with sessions() as db:
        return [public(job) for job in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100))]


@router.post("/api/jobs/{job_id}/retry", dependencies=[Depends(require_operator)])
def retry_job(job_id: str, sessions=Depends(get_sessions), dispatcher: JobDispatcher = Depends(get_dispatcher)):
    with sessions() as db:
        result = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "failed")
            .values(status="queued", error=None, progress=0, attempts=0, started_at=None)
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Only failed jobs may be retried")
        db.commit()
    dispatcher.enqueue(job_id)
    return {"status": "queued"}
