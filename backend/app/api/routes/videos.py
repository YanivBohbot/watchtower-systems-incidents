"""Uploaded videos: list, upload with a watch zone (starts an analysis job), stream the content."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select

from app.api.dependencies import (
    JobDispatcher,
    current_user,
    get_dispatcher,
    get_sessions,
    get_settings,
    get_storage,
    require_operator,
)
from app.api.schemas import public
from app.api.uploads import receive_upload
from app.core.config import Settings
from app.database.models import Job, Video, uid
from app.domain.dwell_rule import Zone
from app.integrations.local_storage import LocalStorage

VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".webm")

router = APIRouter()


@router.get("/api/videos", dependencies=[Depends(current_user)])
def list_videos(sessions=Depends(get_sessions)):
    with sessions() as db:
        return [public(video) for video in db.scalars(select(Video).order_by(Video.created_at.desc()))]


@router.post("/api/videos", status_code=201, dependencies=[Depends(require_operator)])
async def upload_video(
    file: UploadFile = File(...),
    zone: str = Form(...),
    cfg: Settings = Depends(get_settings),
    sessions=Depends(get_sessions),
    storage: LocalStorage = Depends(get_storage),
    dispatcher: JobDispatcher = Depends(get_dispatcher),
):
    try:
        parsed = Zone.model_validate_json(zone)
    except ValidationError:
        raise HTTPException(422, "Invalid normalized rectangle or duration") from None
    ext = Path(file.filename or "").suffix.lower()
    if ext not in VIDEO_EXTENSIONS:
        raise HTTPException(422, "Supported videos: mp4, mov, avi, webm")
    upload, _ = await receive_upload(file, cfg.data_dir, cfg.max_upload_mb)
    video_id, job_id = uid(), uid()
    key = f"videos/{video_id}{ext}"
    storage.put_file(key, upload)
    with sessions() as db:
        video = Video(id=video_id, name=Path(file.filename).name[:255], storage_key=key, zone=parsed.model_dump())
        db.add_all([video, Job(id=job_id, kind="video", resource_id=video_id)])
        db.commit()
        result = public(video)
    dispatcher.enqueue(job_id)
    return {**result, "job_id": job_id}


@router.get("/api/videos/{video_id}/content", dependencies=[Depends(current_user)])
def video_content(video_id: str, sessions=Depends(get_sessions), storage: LocalStorage = Depends(get_storage)):
    with sessions() as db:
        video = db.get(Video, video_id)
        if video is None:
            raise HTTPException(404, "Video not found")
        key = video.storage_key
    return FileResponse(storage.path(key), media_type="video/" + Path(key).suffix.lstrip("."))
