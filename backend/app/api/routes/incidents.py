"""Incidents found by video analysis: list, evidence image, and opening an investigation."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.api.dependencies import (
    JobDispatcher,
    current_user,
    get_dispatcher,
    get_sessions,
    get_storage,
    require_operator,
)
from app.api.schemas import public
from app.database.models import Incident, Investigation, Job, User, uid
from app.integrations.local_storage import LocalStorage

router = APIRouter()


@router.get("/api/incidents", dependencies=[Depends(current_user)])
def list_incidents(sessions=Depends(get_sessions)):
    with sessions() as db:
        return [public(incident) for incident in db.scalars(select(Incident).order_by(Incident.seconds))]


@router.get("/api/incidents/{incident_id}/evidence", dependencies=[Depends(current_user)])
def incident_evidence(incident_id: str, sessions=Depends(get_sessions), storage: LocalStorage = Depends(get_storage)):
    with sessions() as db:
        incident = db.get(Incident, incident_id)
        if incident is None:
            raise HTTPException(404, "Incident not found")
        return Response(storage.read(incident.evidence_key), media_type="image/jpeg")


@router.post("/api/incidents/{incident_id}/investigate", status_code=201)
def investigate_incident(
    incident_id: str,
    user: User = Depends(require_operator),
    sessions=Depends(get_sessions),
    dispatcher: JobDispatcher = Depends(get_dispatcher),
):
    with sessions() as db:
        if db.get(Incident, incident_id) is None:
            raise HTTPException(404, "Incident not found")
        investigation = Investigation(id=uid(), incident_id=incident_id, created_by=user.id)
        job = Job(id=uid(), kind="investigate", resource_id=investigation.id)
        db.add_all([investigation, job])
        db.commit()
        result = public(investigation)
    dispatcher.enqueue(job.id)
    return result
