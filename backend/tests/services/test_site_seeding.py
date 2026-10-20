import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.database.models import Base, Camera, Site
from app.database.session import make_sessions
from app.services.site_seeding import seed_site

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "site-horizon.json"


@pytest.fixture
def sessions(tmp_path):
    engine, sessions = make_sessions(f"sqlite:///{tmp_path}/live.db")
    Base.metadata.create_all(engine)
    yield sessions
    engine.dispose()


def site_data(**camera):
    return {
        "name": "Test site",
        "cameras": [{"name": "hall", "source": "/data/cameras/hall.mp4", "labels": ["hall"], **camera}],
    }


def test_seed_site_is_idempotent_and_updates(sessions):
    seed_site(sessions, site_data())
    seed_site(sessions, site_data(source="/data/cameras/hall-2.mp4", zone={"x1": 0, "y1": 0, "x2": 0.5, "y2": 1}))
    with sessions() as db:
        assert len(list(db.scalars(select(Site)))) == 1
        cameras = list(db.scalars(select(Camera)))
        assert len(cameras) == 1
        assert cameras[0].source == "/data/cameras/hall-2.mp4"
        assert cameras[0].zone["x2"] == 0.5
        assert cameras[0].labels == ["hall"]
        assert cameras[0].enabled is True


def test_seed_site_rejects_invalid_zone(sessions):
    with pytest.raises(ValidationError):
        seed_site(sessions, site_data(zone={"x1": 0.6, "y1": 0, "x2": 0.5, "y2": 1}))
    with sessions() as db:
        assert db.scalar(select(Site)) is None


def test_example_site_is_fictional_and_valid(sessions):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert data["fictional"] is True
    seed_site(sessions, data)
    with sessions() as db:
        names = {c.name for c in db.scalars(select(Camera))}
    assert {"hall", "reception", "corridor", "parking", "kitchen"} <= names


def test_seed_site_cli(tmp_path, monkeypatch):
    from app import cli
    from app.core.config import settings

    monkeypatch.setenv("JWT_SECRET", "cli-test-secret-not-for-production-123456")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/cli.db")
    settings.cache_clear()
    engine, sessions = make_sessions(f"sqlite:///{tmp_path}/cli.db")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("sys.argv", ["cli", "seed-site", str(EXAMPLE)])
    try:
        cli.main()
    finally:
        settings.cache_clear()
    with sessions() as db:
        assert db.scalar(select(Site)).name.startswith("Horizon")
    engine.dispose()
