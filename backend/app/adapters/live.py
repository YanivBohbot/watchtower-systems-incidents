"""Live hub adapters: latest frame and status per camera, plus an alert event channel."""

import queue
import threading
import time


class MemorySubscription:
    def __init__(self, hub):
        self.hub, self.queue = hub, queue.Queue()

    def get(self, timeout: float) -> dict | None:
        try:
            return self.queue.get(timeout=timeout) if timeout > 0 else self.queue.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        with self.hub.lock:
            self.hub.subscribers.discard(self)


class MemoryHub:
    """In-process hub for tests and single-process runs."""

    def __init__(self, frame_ttl: float = 10, clock=time.monotonic):
        self.frame_ttl, self.clock = frame_ttl, clock
        self.frames: dict[str, tuple[float, bytes]] = {}
        self.statuses: dict[str, dict] = {}
        self.subscribers: set[MemorySubscription] = set()
        self.lock = threading.Lock()

    def put_frame(self, camera_id: str, jpeg: bytes) -> None:
        self.frames[camera_id] = (self.clock(), jpeg)

    def get_frame(self, camera_id: str) -> bytes | None:
        stored = self.frames.get(camera_id)
        if stored is None or self.clock() - stored[0] > self.frame_ttl:
            return None
        return stored[1]

    def put_status(self, camera_id: str, status: dict) -> None:
        self.statuses[camera_id] = dict(status)

    def get_status(self, camera_id: str) -> dict | None:
        return self.statuses.get(camera_id)

    def publish(self, event: dict) -> None:
        with self.lock:
            subscribers = list(self.subscribers)
        for subscriber in subscribers:
            subscriber.queue.put(event)

    def subscribe(self) -> MemorySubscription:
        subscription = MemorySubscription(self)
        with self.lock:
            self.subscribers.add(subscription)
        return subscription
