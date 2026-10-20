"""Frame source that replays a recorded video in a loop, standing in for a live camera."""

from pathlib import Path

import cv2


class LoopedVideoSource:
    """A recorded video replayed forever, standing in for a live camera feed."""

    def __init__(self, path):
        self.path = str(Path(path))
        self.cap = cv2.VideoCapture(self.path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if not self.cap.isOpened() or not 0 < self.fps <= 240 or not self.cap.grab():
            self.cap.release()
            raise ValueError(f"Unreadable camera source: {Path(path).name}")
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.loops = 0

    def _rewind(self):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.loops += 1

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            self._rewind()
            ok, frame = self.cap.read()
        return frame if ok else None

    def skip(self, count: int) -> None:
        for _ in range(count):
            if not self.cap.grab():
                self._rewind()
                self.cap.grab()

    def close(self):
        self.cap.release()
