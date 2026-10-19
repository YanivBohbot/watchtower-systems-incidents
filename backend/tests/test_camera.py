import cv2
import numpy as np
import pytest
from sqlalchemy import select

from app.adapters.camera import LoopedVideoSource
from app.adapters.live import MemoryHub
from app.adapters.storage import LocalStorage
from app.adapters.vision import TrackedObject
from app.db import Alert, Base, Camera, Site, make_sessions
from app.services.live import CameraRunner

ZONE = {"x1": 0, "y1": 0, "x2": 1, "y2": 1, "dwell_seconds": 1}


class Clock:
    def __init__(self, step):
        self.value, self.step = 0.0, step

    def __call__(self):
        return self.value

    def tick(self):
        self.value += self.step


class Detector:
    def __init__(self, objects=((1, 0.2, 0.2, 0.4, 0.8, 0.95),)):
        self.objects, self.calls = objects, 0

    def track(self, frame):
        self.calls += 1
        return [TrackedObject(*o) for o in self.objects]


def write_clip(path, frames, fps=10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (64, 48))
    for i in range(frames):
        writer.write(np.full((48, 64, 3), i * 5 % 255, dtype=np.uint8))
    writer.release()
    return path


@pytest.fixture
def live(tmp_path):
    engine, sessions = make_sessions(f"sqlite:///{tmp_path}/live.db")
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add(Site(id="s", name="site"))
        db.flush()
        db.add(Camera(id="cam", site_id="s", name="hall", source="x", labels=[]))
        db.commit()
    yield sessions, LocalStorage(tmp_path / "files"), MemoryHub()
    engine.dispose()


def runner(live, clip, clock, zone=ZONE, detectors=None, source_factory=None):
    sessions, storage, hub = live
    detectors = detectors if detectors is not None else []

    def detector_factory():
        detectors.append(Detector())
        return detectors[-1]

    return CameraRunner(
        "cam",
        zone,
        source_factory or (lambda: LoopedVideoSource(clip)),
        detector_factory,
        hub,
        sessions,
        storage,
        clock=clock,
        analysis_fps=5,
    )


def alerts(sessions):
    with sessions() as db:
        return list(db.scalars(select(Alert)))


def test_frames_are_analyzed_and_published(live, tmp_path):
    clock = Clock(0.2)
    cam = runner(live, write_clip(tmp_path / "c.avi", 30), clock)
    for _ in range(3):
        assert cam.step()
        clock.tick()
    hub = live[2]
    assert hub.get_frame("cam").startswith(b"\xff\xd8")
    assert hub.get_status("cam")["frames_analyzed"] == 3
    assert hub.get_status("cam")["state"] == "live"


def test_dwelling_person_raises_exactly_one_alert(live, tmp_path):
    sessions, storage, hub = live
    clock = Clock(0.2)
    events = hub.subscribe()
    cam = runner(live, write_clip(tmp_path / "c.avi", 30), clock)
    for _ in range(12):
        cam.step()
        clock.tick()
    rows = alerts(sessions)
    assert len(rows) == 1
    assert rows[0].kind == "person_dwell"
    assert rows[0].details["track_id"] == 1
    assert storage.read(rows[0].snapshot_key).startswith(b"\xff\xd8")
    event = events.get(timeout=0)
    assert event["type"] == "alert" and event["alert"]["id"] == rows[0].id
    assert events.get(timeout=0) is None


def test_late_analysis_skips_frames_instead_of_queueing(live, tmp_path):
    clock = Clock(1.0)  # analysis is ten times slower than the 10 fps clip
    detectors = []
    cam = runner(live, write_clip(tmp_path / "c.avi", 100), clock, detectors=detectors)
    for _ in range(4):
        cam.step()
        clock.tick()
    assert detectors[0].calls == 4
    assert cam.position >= 30  # the source advanced with wall-clock time


def test_loop_restart_rebuilds_detector_and_rule(live, tmp_path):
    clock = Clock(0.25)
    detectors = []
    cam = runner(live, write_clip(tmp_path / "c.avi", 20), clock, detectors=detectors)
    for _ in range(20):  # five seconds of a two-second clip
        cam.step()
        clock.tick()
    assert len(detectors) >= 2
    assert len(alerts(live[0])) >= 2  # the recycled track ID alerts again after the loop


def test_camera_without_zone_streams_but_never_alerts(live, tmp_path):
    clock = Clock(0.2)
    cam = runner(live, write_clip(tmp_path / "c.avi", 30), clock, zone=None)
    for _ in range(12):
        cam.step()
        clock.tick()
    assert alerts(live[0]) == []
    assert live[2].get_frame("cam") is not None


def test_unreadable_source_reports_error_without_raising(live, tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    cam = runner(live, bad, Clock(0.2))
    assert cam.step() is False
    status = live[2].get_status("cam")
    assert status["state"] == "error"
    assert status["error"]


def test_memory_hub_frame_expires():
    clock = Clock(0)
    hub = MemoryHub(frame_ttl=10, clock=clock)
    hub.put_frame("cam", b"jpeg")
    clock.value = 9
    assert hub.get_frame("cam") == b"jpeg"
    clock.value = 11
    assert hub.get_frame("cam") is None
