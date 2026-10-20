"""Alerts raised by live cameras: newest first, and their snapshot image."""

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select

from app.api.dependencies import current_user, get_sessions, get_storage
from app.api.schemas import public
from app.database.models import Alert
from app.integrations.local_storage import LocalStorage

router = APIRouter()


@router.get("/api/alerts", dependencies=[Depends(current_user)])
def list_alerts(limit: int = Query(50, ge=1, le=200), sessions=Depends(get_sessions)):
    with sessions() as db:
        rows = db.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(limit))
        # SQLite drops the timezone; stored times are UTC, so say so to the browser.
        return [
            {**public(alert), "created_at": alert.created_at.replace(tzinfo=alert.created_at.tzinfo or timezone.utc)}
            for alert in rows
        ]


@router.get("/api/alerts/{alert_id}/snapshot", dependencies=[Depends(current_user)])
def alert_snapshot(alert_id: str, sessions=Depends(get_sessions), storage: LocalStorage = Depends(get_storage)):
    with sessions() as db:
        alert = db.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(404, "Alert not found")
        key = alert.snapshot_key
    return Response(storage.read(key), media_type="image/jpeg")
