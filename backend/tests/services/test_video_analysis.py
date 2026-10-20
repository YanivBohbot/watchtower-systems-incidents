import cv2
import numpy as np
import pytest
from sqlalchemy import select

from app.database.models import Base, Incident, Video
from app.database.session import make_sessions
from app.integrations.local_storage import LocalStorage
from app.integrations.yolo_detector import TrackedObject
from app.services.video_analysis import VideoService


class Detector:
    def track(self, frame):
        return [TrackedObject(1, 0.2, 0.2, 0.4, 0.8, 0.95)]


def test_real_video_decode_rule_capture_and_retry(tmp_path):
    path = tmp_path / "walk.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (100, 100))
    for _ in range(30):
        writer.write(np.zeros((100, 100, 3), dtype=np.uint8))
    writer.release()
    engine, sessions = make_sessions(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    storage = LocalStorage(tmp_path / "files")
    storage.put("video.avi", path.read_bytes())
    with sessions() as db:
        db.add(
            Video(
                id="video",
                name="walk.avi",
                storage_key="video.avi",
                zone={"x1": 0, "y1": 0, "x2": 1, "y2": 1, "dwell_seconds": 1},
            )
        )
        db.commit()
    service = VideoService(sessions, storage, Detector, max_seconds=10)
    service.analyze("video", lambda _: None)
    service.analyze("video", lambda _: None)
    with sessions() as db:
        incidents = list(db.scalars(select(Incident)))
        assert len(incidents) == 1
        assert incidents[0].seconds == pytest.approx(1.0)
        assert storage.read(incidents[0].evidence_key).startswith(b"\xff\xd8")


def test_invalid_video_fails_explicitly(tmp_path):
    engine, sessions = make_sessions(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    storage = LocalStorage(tmp_path / "files")
    storage.put("bad.mp4", b"bad")
    with sessions() as db:
        db.add(Video(id="bad", name="bad.mp4", storage_key="bad.mp4", zone={"x1": 0, "y1": 0, "x2": 1, "y2": 1}))
        db.commit()
    with pytest.raises(ValueError, match="video"):
        VideoService(sessions, storage, Detector).analyze("bad", lambda _: None)
