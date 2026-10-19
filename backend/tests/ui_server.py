"""Browser-test server only; never used by production Docker entrypoints."""

import tempfile
from pathlib import Path

from app.api import create_app
from app.auth import hash_password
from app.config import Settings
from app.db import Base, User, make_sessions


def build_app():
    root = Path(tempfile.mkdtemp(prefix="watchtower-ui-"))
    cfg = Settings(
        jwt_secret="browser-test-secret-not-for-production-12345",
        data_dir=root,
        database_url=f"sqlite:///{root}/test.db",
    )
    engine, sessions = make_sessions(cfg.database_url)
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add(User(email="ui@test.local", password_hash=hash_password("browser-password-123"), role="operator"))
        db.commit()
    return create_app(cfg, sessions, dispatcher=lambda _: None)
