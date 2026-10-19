"""HTTP adapter: validate input, enforce roles, persist jobs, dispatch IDs."""

import hashlib
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.adapters.storage import LocalStorage
from app.auth import token_for, verify_password
from app.config import Settings
from app.db import Document, Incident, Investigation, Job, User, Video, make_sessions, uid
from app.domain.rules import Zone

log = logging.getLogger(__name__)


class Login(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=1000)


class Review(BaseModel):
    approved: bool
    create_ticket: bool = False


def public(row):
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in ("password_hash", "storage_key", "evidence_key")
    }


def create_app(cfg: Settings, sessions=None, dispatcher=None):
    if sessions is None:
        _, sessions = make_sessions(cfg.database_url)
    storage = LocalStorage(cfg.data_dir / "files")

    @asynccontextmanager
    async def lifespan(_):
        yield

    app = FastAPI(
        title="WatchTower",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.sessions = sessions
    app.add_middleware(CORSMiddleware, allow_origins=[cfg.cors_origin], allow_methods=["*"], allow_headers=["*"])
    bearer = HTTPBearer(auto_error=False)

    def current(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            raise HTTPException(401, "Authentication required")
        try:
            payload = jwt.decode(credentials.credentials, cfg.jwt_secret.get_secret_value(), algorithms=["HS256"])
            with sessions() as db:
                user = db.get(User, payload["sub"])
                if user is None:
                    raise HTTPException(401, "Unknown user")
                return user
        except (jwt.InvalidTokenError, KeyError):
            raise HTTPException(401, "Invalid or expired token") from None

    def operator(user=Depends(current)):
        if user.role not in ("operator", "admin"):
            raise HTTPException(403, "Operator role required")
        return user

    def enqueue(job_id):
        try:
            if dispatcher is not None:
                dispatcher(job_id)
            else:
                from app.tasks import run_job

                run_job.apply_async(
                    args=[job_id],
                    queue="investigation" if job_kind(job_id) in ("investigate", "review") else "processing",
                )
        except Exception:
            # The SQL job is the durable outbox; periodic sweep retries publication.
            log.exception("Queue unavailable; job remains queued: %s", job_id)

    def job_kind(job_id):
        with sessions() as db:
            return db.get(Job, job_id).kind

    async def bounded_upload(file: UploadFile):
        content = bytearray()
        while part := await file.read(1024 * 1024):
            content.extend(part)
            if len(content) > cfg.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, "File exceeds upload limit")
        if not content:
            raise HTTPException(422, "Empty file")
        return bytes(content)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/api/auth/login")
    def login(body: Login):
        with sessions() as db:
            user = db.scalar(select(User).where(User.email == body.email.lower()))
            if user is None or not verify_password(body.password, user.password_hash):
                raise HTTPException(401, "Invalid credentials")
            return {"access_token": token_for(user.id, cfg.jwt_secret.get_secret_value()), "user": public(user)}

    @app.get("/api/me")
    def me(user=Depends(current)):
        return public(user)

    @app.get("/api/videos")
    def videos(user=Depends(current)):
        with sessions() as db:
            return [public(v) for v in db.scalars(select(Video).order_by(Video.created_at.desc()))]

    @app.post("/api/videos", status_code=201)
    async def upload_video(file: UploadFile = File(...), zone: str = Form(...), user=Depends(operator)):
        try:
            parsed = Zone.model_validate_json(zone)
        except ValidationError:
            raise HTTPException(422, "Invalid normalized rectangle or duration") from None
        ext = Path(file.filename or "").suffix.lower()
        if ext not in (".mp4", ".mov", ".avi", ".webm"):
            raise HTTPException(422, "Supported videos: mp4, mov, avi, webm")
        content = await bounded_upload(file)
        video_id, job_id = uid(), uid()
        key = f"videos/{video_id}{ext}"
        storage.put(key, content)
        with sessions() as db:
            video = Video(id=video_id, name=Path(file.filename).name[:255], storage_key=key, zone=parsed.model_dump())
            db.add_all([video, Job(id=job_id, kind="video", resource_id=video_id)])
            db.commit()
            result = public(video)
        enqueue(job_id)
        return {**result, "job_id": job_id}

    @app.get("/api/videos/{video_id}/content")
    def video_content(video_id: str, user=Depends(current)):
        with sessions() as db:
            video = db.get(Video, video_id)
            if video is None:
                raise HTTPException(404, "Video not found")
            return Response(
                storage.read(video.storage_key), media_type="video/" + Path(video.storage_key).suffix.lstrip(".")
            )

    @app.get("/api/jobs")
    def jobs(user=Depends(current)):
        with sessions() as db:
            return [public(j) for j in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100))]

    @app.post("/api/jobs/{job_id}/retry")
    def retry(job_id: str, user=Depends(operator)):
        with sessions() as db:
            result = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "failed")
                .values(status="queued", error=None, progress=0)
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Only failed jobs may be retried")
            db.commit()
        enqueue(job_id)
        return {"status": "queued"}

    @app.get("/api/documents")
    def documents(user=Depends(current)):
        with sessions() as db:
            return [public(d) for d in db.scalars(select(Document))]

    @app.post("/api/documents", status_code=201)
    async def upload_document(file: UploadFile = File(...), user=Depends(operator)):
        if Path(file.filename or "").suffix.lower() not in (".pdf", ".txt"):
            raise HTTPException(422, "Use a text PDF or UTF-8 TXT")
        content = await bounded_upload(file)
        sha = hashlib.sha256(content).hexdigest()
        with sessions() as db:
            existing = db.scalar(select(Document).where(Document.sha256 == sha))
            if existing:
                return public(existing)
            doc_id, job_id = uid(), uid()
            key = f"documents/{doc_id}{Path(file.filename).suffix.lower()}"
            storage.put(key, content)
            doc = Document(id=doc_id, name=Path(file.filename).name[:255], storage_key=key, sha256=sha)
            db.add_all([doc, Job(id=job_id, kind="document", resource_id=doc_id)])
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = db.scalar(select(Document).where(Document.sha256 == sha))
                if existing is None:
                    raise
                storage.delete(key)
                return public(existing)
            result = public(doc)
        enqueue(job_id)
        return result

    @app.get("/api/incidents")
    def incidents(user=Depends(current)):
        with sessions() as db:
            return [public(i) for i in db.scalars(select(Incident).order_by(Incident.seconds))]

    @app.get("/api/incidents/{incident_id}/evidence")
    def evidence(incident_id: str, user=Depends(current)):
        with sessions() as db:
            incident = db.get(Incident, incident_id)
            if incident is None:
                raise HTTPException(404, "Incident not found")
            return Response(storage.read(incident.evidence_key), media_type="image/jpeg")

    @app.post("/api/incidents/{incident_id}/investigate", status_code=201)
    def investigate(incident_id: str, user=Depends(operator)):
        with sessions() as db:
            if db.get(Incident, incident_id) is None:
                raise HTTPException(404, "Incident not found")
            investigation = Investigation(id=uid(), incident_id=incident_id, created_by=user.id)
            job = Job(id=uid(), kind="investigate", resource_id=investigation.id)
            db.add_all([investigation, job])
            db.commit()
            result = public(investigation)
        enqueue(job.id)
        return result

    @app.get("/api/investigations")
    def investigations(user=Depends(current)):
        with sessions() as db:
            return [public(i) for i in db.scalars(select(Investigation))]

    @app.post("/api/investigations/{investigation_id}/review", status_code=202)
    def review(investigation_id: str, body: Review, user=Depends(operator)):
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
            job = Job(id=str(uuid4()), kind="review", resource_id=investigation_id)
            db.add(job)
            db.commit()
        enqueue(job.id)
        return {"status": "review_queued"}

    return app
