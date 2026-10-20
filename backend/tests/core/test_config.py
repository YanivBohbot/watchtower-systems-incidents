import pytest
from pydantic import ValidationError

from app.core.config import Settings

SECRET = "config-test-secret-not-for-production-1234"


def test_yolo_confidence_defaults_to_half():
    assert Settings(jwt_secret=SECRET).yolo_confidence == 0.5


def test_yolo_confidence_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("YOLO_CONFIDENCE", "0.35")
    assert Settings(jwt_secret=SECRET).yolo_confidence == 0.35


@pytest.mark.parametrize("value", [0, 1, 1.5])
def test_yolo_confidence_must_be_strictly_between_zero_and_one(value):
    with pytest.raises(ValidationError):
        Settings(jwt_secret=SECRET, yolo_confidence=value)
