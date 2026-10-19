"""Pure video-time business rule. No YOLO, database or LLM dependency."""

from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator


class Zone(BaseModel):
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)
    dwell_seconds: float = Field(default=5, ge=0.1, le=600)

    @model_validator(mode="after")
    def ordered(self):
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("Zone must have positive width and height")
        return self


@dataclass(frozen=True)
class Observation:
    track_id: int
    x: float
    y: float
    seconds: float


class DwellRule:
    def __init__(self, zone: Zone, max_gap: float = 0.5):
        self.zone = zone
        self.max_gap = max_gap
        self.active: dict[int, tuple[float, float]] = {}
        self.emitted: set[int] = set()

    def feed(self, point: Observation) -> bool:
        z = self.zone
        if point.track_id in self.emitted:
            return False
        inside = z.x1 <= point.x <= z.x2 and z.y1 <= point.y <= z.y2
        if not inside:
            self.active.pop(point.track_id, None)
            return False
        start, last = self.active.get(point.track_id, (point.seconds, point.seconds))
        if point.seconds < last or point.seconds - last > self.max_gap:
            start = point.seconds
        self.active[point.track_id] = (start, point.seconds)
        if point.seconds - start + 1e-6 < z.dwell_seconds:
            return False
        self.emitted.add(point.track_id)
        return True
