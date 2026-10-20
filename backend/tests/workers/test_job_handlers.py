from app.workers import job_handlers


def test_video_job_builds_the_detector_from_settings(app_env, monkeypatch):
    monkeypatch.setenv("YOLO_MODEL", "custom.pt")
    monkeypatch.setenv("YOLO_CONFIDENCE", "0.4")
    built = []

    class Service:
        def __init__(self, sessions, storage, detector_factory, *limits):
            self.detector_factory = detector_factory

        def analyze(self, video_id, progress):
            self.detector_factory()

    monkeypatch.setattr(job_handlers, "VideoService", Service)
    monkeypatch.setattr(job_handlers, "YoloDetector", lambda *args, **kwargs: built.append((args, kwargs)))
    job_handlers.execute("video", "v", lambda _: None)
    assert built == [(("custom.pt",), {"confidence": 0.4})]
