"""Browser-test server only; never used by production Docker entrypoints."""

import tempfile
from pathlib import Path

import cv2
import numpy as np

from app.integrations.live_hub import MemoryHub
from app.api.application import create_app
from app.core.security import hash_password
from app.core.config import Settings
from app.database.models import Alert, Base, Camera, Site, User
from app.database.session import make_sessions
from app.services.camera_monitor import alert_payload


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
        db.add(Site(id="site", name="Test site"))
        db.flush()
        db.add(Camera(id="cam-hall", site_id="site", name="hall", source="hall.mp4", labels=["hall"]))
        db.commit()
    hub = MemoryHub(frame_ttl=10**9)
    frame = np.full((90, 160, 3), 60, dtype=np.uint8)
    hub.put_frame("cam-hall", cv2.imencode(".jpg", frame)[1].tobytes())
    hub.put_status("cam-hall", {"state": "live", "frames_analyzed": 1200, "analysis_fps": 5, "error": None})
    app = create_app(cfg, sessions, dispatcher=lambda _: None, hub=hub)

    @app.post("/api/test/alert")
    def raise_test_alert():
        """Stands in for the camera process so the browser test can watch a pushed alert arrive."""
        with sessions() as db:
            alert = Alert(
                camera_id="cam-hall", kind="person_dwell", snapshot_key="none.jpg", details={"confidence": 0.91}
            )
            db.add(alert)
            db.commit()
            payload = alert_payload(alert)
        hub.publish({"type": "alert", "alert": payload})
        return payload

    return app
