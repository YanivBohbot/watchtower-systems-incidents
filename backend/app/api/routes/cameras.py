"""Live cameras: list with their live status, and the latest analyzed frame."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.api.dependencies import call_live_hub, current_user, get_hub, get_sessions
from app.api.schemas import public
from app.database.models import Camera, Site

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/cameras", dependencies=[Depends(current_user)])
def list_cameras(sessions=Depends(get_sessions), hub=Depends(get_hub)):
    with sessions() as db:
        rows = db.execute(select(Camera, Site.name).join(Site).order_by(Site.name, Camera.name)).all()
        result = [{**public(camera), "site": site} for camera, site in rows]
    for camera in result:
        # The list stays usable while Redis is down; only the live status goes missing.
        try:
            camera["status"] = hub.get_status(camera["id"])
        except Exception:
            log.warning("Live hub unavailable", exc_info=True)
            camera["status"] = None
    return result


@router.get("/api/cameras/{camera_id}/frame", dependencies=[Depends(current_user)])
def camera_frame(camera_id: str, hub=Depends(get_hub)):
    frame = call_live_hub(hub.get_frame, camera_id)
    if frame is None:
        raise HTTPException(404, "No recent frame")
    return Response(frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
