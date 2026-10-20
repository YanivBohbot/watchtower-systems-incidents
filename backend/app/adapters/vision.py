from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrackedObject:
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


class YoloDetector:
    """One model/tracker instance per video; no tracker state shared across jobs."""

    def __init__(self, model_path="yolov8n.pt"):
        from ultralytics import YOLO

        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        self.model_path = model_path
        self.model = YOLO(model_path)

    def reset(self) -> None:
        """Forget tracks (for example when a looped video restarts) without reloading the weights."""
        predictor = getattr(self.model, "predictor", None)
        for tracker in getattr(predictor, "trackers", None) or []:
            tracker.reset()

    def track(self, frame) -> list[TrackedObject]:
        result = self.model.track(frame, persist=True, classes=[0], conf=0.5, tracker="bytetrack.yaml", verbose=False)[
            0
        ]
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            return []
        return [
            TrackedObject(int(track_id), *map(float, xyxy), float(confidence))
            for track_id, xyxy, confidence in zip(
                boxes.id.tolist(), boxes.xyxyn.tolist(), boxes.conf.tolist(), strict=True
            )
        ]
