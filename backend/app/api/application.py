"""Application factory: builds the FastAPI app, stores shared services on app.state, mounts the routers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import JobDispatcher
from app.api.routes import (
    alerts,
    auth,
    cameras,
    documents,
    health,
    incidents,
    investigations,
    jobs,
    live_events,
    videos,
)
from app.core.config import Settings
from app.database.session import make_sessions
from app.integrations.local_storage import LocalStorage

ROUTERS = (health, auth, videos, jobs, documents, incidents, investigations, cameras, alerts, live_events)


def create_app(cfg: Settings, sessions=None, dispatcher=None, hub=None) -> FastAPI:
    """Tests inject `sessions`, a `dispatcher` that records job IDs, and an in-memory `hub`."""
    if sessions is None:
        _, sessions = make_sessions(cfg.database_url)
    if hub is None:
        from app.integrations.live_hub import RedisHub

        hub = RedisHub(cfg.redis_url)  # connects lazily; live routes answer 503 while Redis is down

    app = FastAPI(
        title="WatchTower",
        version=health.API_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = cfg
    app.state.sessions = sessions
    app.state.storage = LocalStorage(cfg.data_dir / "files")
    app.state.hub = hub
    app.state.dispatcher = JobDispatcher(sessions, dispatcher)
    app.add_middleware(CORSMiddleware, allow_origins=[cfg.cors_origin], allow_methods=["*"], allow_headers=["*"])
    for module in ROUTERS:
        app.include_router(module.router)
    return app
