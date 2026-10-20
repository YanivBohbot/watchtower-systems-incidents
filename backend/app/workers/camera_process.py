"""Camera process: one runner thread per enabled camera. Run with `python -m app.workers.camera_process`."""

import logging
import signal
import threading
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.database.models import Camera
from app.database.session import make_sessions
from app.integrations.live_hub import RedisHub
from app.integrations.local_storage import LocalStorage
from app.integrations.looped_video_source import LoopedVideoSource
from app.services.camera_monitor import CameraRunner

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
    from app.integrations.yolo_detector import YoloDetector

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
