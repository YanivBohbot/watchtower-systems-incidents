"""Shared FastAPI dependencies: services stored on app.state, the signed-in user, role checks, job dispatch."""

import logging

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.database.models import Job, User
from app.integrations.local_storage import LocalStorage

log = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


class JobDispatcher:
    """Publish a job to its Celery queue.

    The SQL job row is the durable outbox: when the queue is unavailable the job stays queued
    and the periodic sweep publishes it later. Tests pass `dispatcher` to record job IDs instead.
    """

    def __init__(self, sessions, dispatcher=None):
        self.sessions, self.dispatcher = sessions, dispatcher

    def enqueue(self, job_id: str) -> None:
        try:
            if self.dispatcher is not None:
                self.dispatcher(job_id)
            else:
                from app.workers.job_queue import queue_for_kind, run_job

                with self.sessions() as db:
                    kind = db.get(Job, job_id).kind
                run_job.apply_async(args=[job_id], queue=queue_for_kind(kind))
        except Exception:
            log.exception("Queue unavailable; job remains queued: %s", job_id)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_sessions(request: Request):
    return request.app.state.sessions


def get_storage(request: Request) -> LocalStorage:
    return request.app.state.storage


def get_hub(request: Request):
    return request.app.state.hub


def get_dispatcher(request: Request) -> JobDispatcher:
    return request.app.state.dispatcher


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    cfg: Settings = Depends(get_settings),
    sessions=Depends(get_sessions),
) -> User:
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


def require_operator(user: User = Depends(current_user)) -> User:
    if user.role not in ("operator", "admin"):
        raise HTTPException(403, "Operator role required")
    return user


def call_live_hub(call, *args):
    """Call the live hub; answer 503 instead of 500 while Redis is unreachable."""
    try:
        return call(*args)
    except Exception:
        log.warning("Live hub unavailable", exc_info=True)
        raise HTTPException(503, "Live service unavailable") from None
