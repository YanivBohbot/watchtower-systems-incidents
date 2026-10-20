"""Uploaded-video analysis: track people, apply the dwell rule, record incidents with evidence."""

import tempfile
from pathlib import Path

import cv2
from sqlalchemy import select

from app.database.models import Incident, Video, uid
from app.domain.dwell_rule import DwellRule, Observation, Zone
from app.services.frame_annotation import annotate, encode_jpeg


class VideoService:
    def __init__(self, sessions, storage, detector_factory, max_seconds=180, max_pixels=3840 * 2160):
        self.sessions, self.storage, self.detector_factory = sessions, storage, detector_factory
        self.max_seconds, self.max_pixels = max_seconds, max_pixels

    def analyze(self, video_id, progress):
        with self.sessions() as db:
            video = db.get(Video, video_id)
            if video is None:
                raise ValueError("Unknown video")
            zone = Zone.model_validate(video.zone)
            existing = set(db.scalars(select(Incident.track_id).where(Incident.video_id == video_id)))
            with tempfile.TemporaryDirectory() as temp:
                path = self.storage.local_copy(video.storage_key, Path(temp) / Path(video.storage_key).name)
                cap = cv2.VideoCapture(str(path))
                try:
                    fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    if not cap.isOpened() or not 0 < fps <= 240 or count <= 0:
                        raise ValueError("Invalid or unsupported video")
                    if count / fps > self.max_seconds:
                        raise ValueError(f"Maximum video duration: {self.max_seconds}s")
                    if cap.get(cv2.CAP_PROP_FRAME_WIDTH) * cap.get(cv2.CAP_PROP_FRAME_HEIGHT) > self.max_pixels:
                        raise ValueError("Video resolution exceeds limit")
                    detector = self.detector_factory()
                    rule = DwellRule(zone, max_gap=max(0.5, 2 / fps))
                    n = 0
                    while True:
                        ok, frame = cap.read()
                        if not ok:
                            break
                        seconds = n / fps
                        if seconds > self.max_seconds:
                            raise ValueError("Decoded video exceeds duration limit")
                        for obj in detector.track(frame):
                            observation = Observation(obj.track_id, (obj.x1 + obj.x2) / 2, obj.y2, seconds)
                            if not rule.feed(observation) or obj.track_id in existing:
                                continue
                            evidence = annotate(frame, zone.model_dump(), [(obj.x1, obj.y1, obj.x2, obj.y2)])
                            incident_id = uid()
                            key = f"evidence/{incident_id}.jpg"
                            self.storage.put(key, encode_jpeg(evidence))
                            db.add(
                                Incident(
                                    id=incident_id,
                                    video_id=video_id,
                                    track_id=obj.track_id,
                                    seconds=seconds,
                                    evidence_key=key,
                                    details={
                                        "rule": "zone_dwell",
                                        "zone": zone.model_dump(),
                                        "confidence": obj.confidence,
                                        "point": "bottom_center",
                                        "model": getattr(detector, "model_path", type(detector).__name__),
                                    },
                                )
                            )
                            db.commit()
                            existing.add(obj.track_id)
                        n += 1
                        if n % 30 == 0:
                            progress(min(99, int(n / count * 100)))
                    if n == 0 or n < count * 0.9:
                        raise ValueError("Empty or truncated video")
                finally:
                    cap.release()
