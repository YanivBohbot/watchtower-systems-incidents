import os

import cv2
import numpy as np
import pytest
from sqlalchemy import select

from app.database.models import Alert, Base, Camera, Site
from app.database.session import make_sessions
from app.integrations.live_hub import MemoryHub
from app.integrations.local_storage import LocalStorage
from app.integrations.looped_video_source import LoopedVideoSource
from app.integrations.yolo_detector import TrackedObject
from app.services.camera_monitor import CameraRunner

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
        self.objects, self.calls, self.resets = objects, 0, 0

    def track(self, frame):
        self.calls += 1
        return [TrackedObject(*o) for o in self.objects]

    def reset(self):
        self.resets += 1


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


def test_loop_restart_resets_tracker_and_rule_without_reloading_model(live, tmp_path):
    clock = Clock(0.25)
    detectors = []
    cam = runner(live, write_clip(tmp_path / "c.avi", 20), clock, detectors=detectors)
    for _ in range(20):  # five seconds of a two-second clip
        cam.step()
        clock.tick()
    assert len(detectors) == 1  # weights are loaded once per camera
    assert detectors[0].resets >= 2
    assert len(alerts(live[0])) >= 2  # the recycled track ID alerts again after the loop


def test_slow_analysis_still_raises_dwell_alert(live, tmp_path):
    clock = Clock(1.5)  # each step takes longer than the nominal analysis budget
    cam = runner(live, write_clip(tmp_path / "c.avi", 100), clock)
    for _ in range(4):
        cam.step()
        clock.tick()
    assert len(alerts(live[0])) == 1


class BrokenHub:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise ConnectionError("redis down")

        return fail


def test_hub_outage_never_kills_the_camera_thread(live, tmp_path):
    import threading

    sessions, storage, _ = live
    cam = CameraRunner(
        "cam",
        ZONE,
        lambda: LoopedVideoSource(write_clip(tmp_path / "c.avi", 30)),
        Detector,
        BrokenHub(),
        sessions,
        storage,
        clock=Clock(0.2),
        analysis_fps=5,
    )
    assert cam.step() is False  # no exception escapes
    stop = threading.Event()
    thread = threading.Thread(target=cam.run, args=(stop, 0.01))
    thread.start()
    thread.join(timeout=0.3)
    assert thread.is_alive()  # still retrying
    stop.set()
    thread.join(timeout=5)


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


def test_build_runners_only_for_enabled_cameras(live, tmp_path):
    from app.workers.camera_process import build_runners

    sessions, storage, hub = live
    with sessions() as db:
        db.add(Camera(id="off", site_id="s", name="parking", source="y", labels=[], enabled=False))
        db.commit()
    runners = build_runners(sessions, storage, hub, Detector, analysis_fps=5)
    assert [r.camera_id for r in runners] == ["cam"]


@pytest.mark.skipif(not os.environ.get("WATCHTOWER_TEST_REDIS_URL"), reason="needs Redis")
def test_redis_hub_round_trip():
    from app.integrations.live_hub import RedisHub

    hub = RedisHub(os.environ["WATCHTOWER_TEST_REDIS_URL"])
    events = hub.subscribe()
    hub.put_frame("cam-test", b"jpeg")
    hub.put_status("cam-test", {"state": "live", "frames_analyzed": 3})
    hub.publish({"type": "alert", "alert": {"id": "a"}})
    assert hub.get_frame("cam-test") == b"jpeg"
    assert hub.get_status("cam-test")["frames_analyzed"] == 3
    assert events.get(timeout=2)["alert"]["id"] == "a"
    events.close()
