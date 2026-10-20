"""One live camera: paced frame reading, detection, dwell rule, alerts pushed to the hub."""

import logging
import time
from datetime import datetime, timezone

from app.database.models import Alert, uid
from app.domain.dwell_rule import DwellRule, Observation, Zone
from app.services.frame_annotation import annotate, encode_jpeg

log = logging.getLogger(__name__)


def alert_payload(alert) -> dict:
    return {
        "id": alert.id,
        "camera_id": alert.camera_id,
        "kind": alert.kind,
        "status": alert.status,
        "created_at": alert.created_at.isoformat(),
        "details": alert.details,
    }


class CameraRunner:
    def __init__(
        self,
        camera_id,
        zone: dict | None,
        source_factory,
        detector_factory,
        hub,
        sessions,
        storage,
        clock=time.monotonic,
        analysis_fps: float = 5,
    ):
        self.camera_id, self.zone = camera_id, zone
        self.source_factory, self.detector_factory = source_factory, detector_factory
        self.hub, self.sessions, self.storage = hub, sessions, storage
        self.clock, self.analysis_fps = clock, analysis_fps
        self.source = self.detector = None
        self.frames_analyzed = 0
        self.position = 0  # frames consumed from the source since it was opened
        self.last_step = None

    def _open(self):
        self.source = self.source_factory()
        self.started, self.position, self.loops = self.clock(), 0, self.source.loops
        if self.detector is None:
            self.detector = self.detector_factory()  # loads model weights: once per camera
        self._reset()

    def _close(self):
        if self.source is not None and hasattr(self.source, "close"):
            self.source.close()
        self.source = None

    def _reset(self):
        """Tracker IDs restart with the video, so the tracker and the rule restart too."""
        if hasattr(self.detector, "reset"):
            self.detector.reset()
        self.rule = DwellRule(Zone.model_validate(self.zone)) if self.zone else None

    def _status(self, state, error=None):
        try:
            self.hub.put_status(
                self.camera_id,
                {
                    "state": state,
                    "frames_analyzed": self.frames_analyzed,
                    "analysis_fps": self.analysis_fps,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "error": error,
                },
            )
        except Exception:
            log.warning("Camera %s: live hub unavailable", self.camera_id, exc_info=True)

    def step(self) -> bool:
        """Analyze the frame matching the current wall-clock time; late frames are skipped, never queued."""
        try:
            if self.source is None:
                self._open()
            target = int((self.clock() - self.started) * self.source.fps)
            if target > self.position:
                self.source.skip(target - self.position)
                self.position = target
            frame = self.source.read()
            if frame is None:
                raise ValueError("Camera source stopped returning frames")
            self.position += 1
            if self.source.loops != self.loops:
                self.loops = self.source.loops
                self._reset()
            now = self.clock()
            if self.rule is not None:
                # A track counts as continuous across one slow step, so slow analysis delays alerts
                # instead of silently preventing them.
                interval = now - self.last_step if self.last_step is not None else 0
                self.rule.max_gap = max(1.0, 3 / self.analysis_fps, 2.5 * interval)
            self.last_step = now
            self._analyze(frame, self.position / self.source.fps)
        except Exception as error:
            log.exception("Camera %s failed", self.camera_id)
            self._close()
            self._status("error", f"{type(error).__name__}: {error}")
            return False
        self.frames_analyzed += 1
        self._status("live")
        return True

    def _analyze(self, frame, seconds):
        objects = self.detector.track(frame)
        boxes = [(o.x1, o.y1, o.x2, o.y2) for o in objects]
        self.hub.put_frame(self.camera_id, encode_jpeg(annotate(frame, self.zone, boxes)))
        if self.rule is None:
            return
        for obj in objects:
            if self.rule.feed(Observation(obj.track_id, (obj.x1 + obj.x2) / 2, obj.y2, seconds)):
                self._raise_alert(frame, obj)

    def _raise_alert(self, frame, obj):
        alert_id = uid()
        key = f"alerts/{alert_id}.jpg"
        self.storage.put(key, encode_jpeg(annotate(frame, self.zone, [(obj.x1, obj.y1, obj.x2, obj.y2)])))
        details = {
            "rule": "zone_dwell",
            "track_id": obj.track_id,
            "box": [obj.x1, obj.y1, obj.x2, obj.y2],
            "confidence": obj.confidence,
            "zone": self.zone,
        }
        with self.sessions() as db:
            alert = Alert(id=alert_id, camera_id=self.camera_id, kind="person_dwell", snapshot_key=key, details=details)
            db.add(alert)
            db.commit()
            payload = alert_payload(alert)
        self.hub.publish({"type": "alert", "alert": payload})

    def run(self, stop, retry_seconds: float = 5) -> None:
        """Loop until `stop` (a threading.Event) is set; a failing source is retried, never fatal."""
        while not stop.is_set():
            began = self.clock()
            try:
                ok = self.step()
            except Exception:  # never let one bad step end the camera thread
                log.exception("Camera %s: unexpected error", self.camera_id)
                ok = False
            if not ok:
                stop.wait(retry_seconds)
                continue
            stop.wait(max(0.0, 1 / self.analysis_fps - (self.clock() - began)))
