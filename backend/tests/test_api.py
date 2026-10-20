import io
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.core.security import hash_password
from app.core.security import token_for
from app.integrations.local_storage import LocalStorage
from app.core.config import Settings
from app.database.models import Base, Job, User
from app.database.session import make_sessions


@pytest.fixture
def app_client(tmp_path):
    yield from make_client(tmp_path)


def make_client(tmp_path, **overrides):
    cfg = Settings(jwt_secret="x" * 40, data_dir=tmp_path, database_url=f"sqlite:///{tmp_path}/api.db", **overrides)
    engine, sessions = make_sessions(cfg.database_url)
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add_all(
            [
                User(
                    id="op",
                    email="operator@test.local",
                    role="operator",
                    password_hash=hash_password("password-long-123"),
                ),
                User(
                    id="view",
                    email="viewer@test.local",
                    role="viewer",
                    password_hash=hash_password("password-long-123"),
                ),
            ]
        )
        db.commit()
    queued = []
    app = create_app(cfg, sessions, dispatcher=queued.append)
    with TestClient(app) as client:
        yield client, queued


def login(client, email="operator@test.local"):
    response = client.post("/api/auth/login", json={"email": email, "password": "password-long-123"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_auth_and_roles(app_client):
    client, _ = app_client
    assert client.get("/api/videos").status_code == 401
    assert client.post("/api/auth/login", json={"email": "none", "password": "wrong"}).status_code == 401
    headers = login(client, "viewer@test.local")
    assert client.get("/api/videos", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/videos",
            headers=headers,
            files={"file": ("x.mp4", b"video")},
            data={"zone": '{"x1":0,"y1":0,"x2":1,"y2":1}'},
        ).status_code
        == 403
    )


def test_upload_commits_job_and_rejects_invalid_zone(app_client):
    client, queued = app_client
    headers = login(client)
    files = {"file": ("walk.mp4", io.BytesIO(b"not-real-video"), "video/mp4")}
    response = client.post(
        "/api/videos", headers=headers, files=files, data={"zone": '{"x1":0,"y1":0,"x2":1,"y2":1,"dwell_seconds":2}'}
    )
    assert response.status_code == 201
    video = response.json()
    assert len(queued) == 1
    assert client.get("/api/jobs", headers=headers).json()[0]["status"] == "queued"
    assert client.get(f"/api/videos/{video['id']}/content").status_code == 401
    assert client.get(f"/api/videos/{video['id']}/content", headers=headers).content == b"not-real-video"
    assert (
        client.post("/api/videos", headers=headers, files={"file": ("x.mp4", b"x")}, data={"zone": "{}"}).status_code
        == 422
    )


def test_document_deduplication_and_retry_role(app_client):
    client, queued = app_client
    headers = login(client)
    for _ in range(2):
        response = client.post("/api/documents", headers=headers, files={"file": ("rules.txt", b"Zone A procedure")})
        assert response.status_code in (200, 201)
    assert len(queued) == 1
    assert client.get("/api/documents", headers=headers).json()[0]["name"] == "rules.txt"
    assert client.post("/api/jobs/missing/retry", headers=login(client, "viewer@test.local")).status_code == 403


def test_concurrent_identical_documents_return_same_resource(app_client, monkeypatch):
    client, queued = app_client
    barrier = Barrier(2)
    original = LocalStorage.put_file

    def synchronized_put(self, key, source):
        if key.startswith("documents/"):
            barrier.wait(timeout=5)
        return original(self, key, source)

    monkeypatch.setattr(LocalStorage, "put_file", synchronized_put)
    headers = {"Authorization": "Bearer " + token_for("op", "x" * 40)}

    def upload(_):
        with TestClient(client.app, raise_server_exceptions=False) as concurrent:
            return concurrent.post("/api/documents", headers=headers, files={"file": ("same.txt", b"same procedure")})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(upload, range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert len(queued) == 1


ZONE = '{"x1":0,"y1":0,"x2":1,"y2":1,"dwell_seconds":2}'


def test_video_content_supports_range_requests(app_client):
    client, _ = app_client
    headers = login(client)
    files = {"file": ("walk.mp4", io.BytesIO(b"0123456789" * 100), "video/mp4")}
    video = client.post("/api/videos", headers=headers, files=files, data={"zone": ZONE}).json()
    response = client.get(f"/api/videos/{video['id']}/content", headers={**headers, "Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.content == b"0123456789"


def test_oversized_upload_leaves_no_temp_file(tmp_path):
    for client, queued in make_client(tmp_path, max_upload_mb=1):
        files = {"file": ("big.mp4", io.BytesIO(b"x" * (1024 * 1024 + 1)), "video/mp4")}
        response = client.post("/api/videos", headers=login(client), files=files, data={"zone": ZONE})
        assert response.status_code == 413
        assert queued == []
    assert list((tmp_path / "uploads").glob("*")) == []


def test_retry_resets_attempts(app_client):
    client, queued = app_client
    sessions = client.app.state.sessions
    with sessions() as db:
        db.add(Job(id="failed-job", kind="video", resource_id="v", status="failed", attempts=2, error="boom"))
        db.commit()
    assert client.post("/api/jobs/failed-job/retry", headers=login(client)).status_code == 200
    with sessions() as db:
        row = db.get(Job, "failed-job")
        assert row.attempts == 0
        assert row.started_at is None


@pytest.fixture
def live_client(tmp_path):
    from app.integrations.live_hub import MemoryHub
    from app.database.models import Alert, Camera, Site

    hub = MemoryHub()
    cfg = Settings(jwt_secret="x" * 40, data_dir=tmp_path, database_url=f"sqlite:///{tmp_path}/api.db")
    engine, sessions = make_sessions(cfg.database_url)
    Base.metadata.create_all(engine)
    storage = LocalStorage(tmp_path / "files")
    storage.put("alerts/a2.jpg", b"\xff\xd8snapshot")
    with sessions() as db:
        db.add(
            User(id="view", email="viewer@test.local", role="viewer", password_hash=hash_password("password-long-123"))
        )
        db.add(Site(id="s", name="site"))
        db.flush()
        db.add(Camera(id="cam", site_id="s", name="hall", source="hall.mp4", labels=["hall"]))
        db.flush()
        for alert_id, created in (("a1", "2026-10-19T10:00:00+00:00"), ("a2", "2026-10-19T11:00:00+00:00")):
            db.add(
                Alert(
                    id=alert_id,
                    camera_id="cam",
                    kind="person_dwell",
                    created_at=datetime.fromisoformat(created),
                    snapshot_key=f"alerts/{alert_id}.jpg",
                    details={"track_id": 1},
                )
            )
        db.commit()
    with TestClient(create_app(cfg, sessions, dispatcher=lambda _: None, hub=hub)) as client:
        yield client, hub, login(client, "viewer@test.local")


def test_live_routes_require_auth(live_client):
    client, _, _ = live_client
    for path in (
        "/api/cameras",
        "/api/cameras/cam/frame",
        "/api/alerts",
        "/api/alerts/a2/snapshot",
        "/api/live/events",
    ):
        assert client.get(path).status_code == 401, path


def test_cameras_list_includes_live_status(live_client):
    client, hub, headers = live_client
    hub.put_status("cam", {"state": "live", "frames_analyzed": 42})
    cameras = client.get("/api/cameras", headers=headers).json()
    assert cameras[0]["name"] == "hall"
    assert cameras[0]["status"]["frames_analyzed"] == 42
    assert "source" not in cameras[0]


def test_camera_frame_404_until_published(live_client):
    client, hub, headers = live_client
    assert client.get("/api/cameras/cam/frame", headers=headers).status_code == 404
    hub.put_frame("cam", b"\xff\xd8frame")
    response = client.get("/api/cameras/cam/frame", headers=headers)
    assert response.status_code == 200
    assert response.content == b"\xff\xd8frame"
    assert response.headers["cache-control"] == "no-store"


def test_alerts_newest_first_and_snapshot(live_client):
    client, _, headers = live_client
    assert [a["id"] for a in client.get("/api/alerts", headers=headers).json()] == ["a2", "a1"]
    assert "snapshot_key" not in client.get("/api/alerts", headers=headers).json()[0]
    # SQLite returns naive datetimes; the browser must not read them as local time.
    assert client.get("/api/alerts", headers=headers).json()[0]["created_at"] == "2026-10-19T11:00:00+00:00"
    assert client.get("/api/alerts/a2/snapshot", headers=headers).content == b"\xff\xd8snapshot"
    assert client.get("/api/alerts/nope/snapshot", headers=headers).status_code == 404


def test_live_events_stream_pushes_alerts(live_client):
    client, hub, headers = live_client
    with client.stream("GET", "/api/live/events", headers=headers) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = response.iter_lines()
        assert next(lines) == ": connected"
        hub.publish({"type": "alert", "alert": {"id": "new"}})
        received = [next(lines) for _ in range(3)]
    assert received[1] == "event: alert"
    assert received[2].startswith("data: ") and '"new"' in received[2]


def test_live_routes_return_503_when_hub_is_down(live_client):
    client, hub, headers = live_client

    def down(*_):
        raise ConnectionError("redis down")

    hub.get_frame = hub.get_status = down
    assert client.get("/api/cameras/cam/frame", headers=headers).status_code == 503
    cameras = client.get("/api/cameras", headers=headers)
    assert cameras.status_code == 200 and cameras.json()[0]["status"] is None


def test_live_events_end_cleanly_when_hub_fails_mid_stream(live_client):
    client, hub, headers = live_client

    class Failing:
        def get(self, timeout):
            raise ConnectionError("redis down")

        def close(self):
            self.closed = True

    failing = Failing()
    hub.subscribe = lambda: failing
    with client.stream("GET", "/api/live/events", headers=headers) as response:
        assert list(response.iter_lines()) == [": connected", ""]
    assert failing.closed
