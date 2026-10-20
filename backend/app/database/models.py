"""ORM tables for users, videos, jobs, incidents, procedures, investigations, sites, cameras and alerts."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(default="operator")


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    storage_key: Mapped[str]
    zone: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    kind: Mapped[str]
    resource_id: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    progress: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (UniqueConstraint("video_id", "track_id", name="uq_video_track"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"))
    track_id: Mapped[int]
    seconds: Mapped[float]
    evidence_key: Mapped[str]
    details: Mapped[dict] = mapped_column(JSON)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    storage_key: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    sha256: Mapped[str] = mapped_column(String(64), unique=True)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    page: Mapped[int]
    text: Mapped[str]


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    status: Mapped[str] = mapped_column(default="queued")
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decision: Mapped[str | None]
    ticket: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (UniqueConstraint("site_id", "name", name="uq_site_camera"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str]
    zone: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(default=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"))
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    snapshot_key: Mapped[str]
    details: Mapped[dict] = mapped_column(JSON)
