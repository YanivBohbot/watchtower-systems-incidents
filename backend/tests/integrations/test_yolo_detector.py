import sys
import types

import pytest

from app.integrations.yolo_detector import YoloDetector


class FakeModel:
    def __init__(self, path):
        self.path, self.calls = path, []

    def track(self, frame, **kwargs):
        self.calls.append(kwargs)
        return [types.SimpleNamespace(boxes=None)]


@pytest.fixture
def fake_ultralytics(monkeypatch):
    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=FakeModel))


def test_confidence_threshold_is_passed_to_the_model(fake_ultralytics, tmp_path):
    detector = YoloDetector(str(tmp_path / "m.pt"), confidence=0.3)
    assert detector.track(object()) == []
    call = detector.model.calls[0]
    assert call["conf"] == 0.3
    assert call["classes"] == [0]


def test_default_confidence_threshold_is_half(fake_ultralytics, tmp_path):
    detector = YoloDetector(str(tmp_path / "m.pt"))
    detector.track(object())
    assert detector.model.calls[0]["conf"] == 0.5
