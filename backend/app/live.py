"""Camera process: one runner thread per enabled camera. Run with `python -m app.live`."""

import logging
import signal
import threading
from pathlib import Path

from sqlalchemy import select

from app.adapters.camera import LoopedVideoSource
from app.adapters.live import RedisHub
from app.adapters.storage import LocalStorage
from app.config import settings
from app.db import Camera, make_sessions
from app.services.live import CameraRunner

log = logging.getLogger(__name__)


def build_runners(sessions, storage, hub, detector_factory, analysis_fps, cameras_dir: Path = Path(".")):
    with sessions() as db:
        cameras = list(db.scalars(select(Camera).where(Camera.enabled.is_(True)).order_by(Camera.name)))
    runners = []
    for camera in cameras:
        source = Path(camera.source) if Path(camera.source).is_absolute() else cameras_dir / camera.source
        runners.append(
            CameraRunner(
                camera.id,
                camera.zone,
                lambda path=source: LoopedVideoSource(path),
                detector_factory,
                hub,
                sessions,
                storage,
                analysis_fps=analysis_fps,
            )
        )
    return runners


def main():
    logging.basicConfig(level=logging.INFO)
    cfg = settings()
    from app.adapters.vision import YoloDetector

    engine, sessions = make_sessions(cfg.database_url)
    runners = build_runners(
        sessions,
        LocalStorage(cfg.data_dir / "files"),
        RedisHub(cfg.redis_url),
        lambda: YoloDetector(cfg.yolo_model),
        cfg.live_analysis_fps,
        cfg.cameras_dir or cfg.data_dir / "cameras",
    )
    if not runners:
        log.warning("No enabled camera; run `python -m app.cli seed-site FILE` first")
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    threads = [threading.Thread(target=r.run, args=(stop,), name=r.camera_id, daemon=True) for r in runners]
    for thread in threads:
        thread.start()
    log.info("Watching %d camera(s)", len(threads))
    stop.wait()
    for thread in threads:
        thread.join(timeout=10)
    engine.dispose()


if __name__ == "__main__":
    main()
