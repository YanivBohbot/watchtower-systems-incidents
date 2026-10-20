"""Investigations: list them, and record the human review that resumes the paused workflow."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update

from app.api.dependencies import JobDispatcher, current_user, get_dispatcher, get_sessions, require_operator
from app.api.schemas import Review, public
from app.database.models import Investigation, Job, User, uid

router = APIRouter()


@router.get("/api/investigations", dependencies=[Depends(current_user)])
def list_investigations(sessions=Depends(get_sessions)):
    with sessions() as db:
        return [public(investigation) for investigation in db.scalars(select(Investigation))]


@router.post("/api/investigations/{investigation_id}/review", status_code=202)
def review_investigation(
    investigation_id: str,
    body: Review,
    user: User = Depends(require_operator),
    sessions=Depends(get_sessions),
    dispatcher: JobDispatcher = Depends(get_dispatcher),
):
    if body.create_ticket and not body.approved:
        raise HTTPException(422, "Cannot publish a rejected report")
    with sessions() as db:
        result = db.execute(
            update(Investigation)
            .where(Investigation.id == investigation_id, Investigation.status == "awaiting_review")
            .values(status="review_queued", decision=json.dumps(body.model_dump()), reviewed_by=user.id)
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Investigation is not awaiting review")
        job = Job(id=uid(), kind="review", resource_id=investigation_id)
        db.add(job)
        db.commit()
    dispatcher.enqueue(job.id)
    return {"status": "review_queued"}
