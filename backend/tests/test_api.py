import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.auth import hash_password
from app.auth import token_for
from app.adapters.storage import LocalStorage
from app.config import Settings
from app.db import Base, User, make_sessions


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
