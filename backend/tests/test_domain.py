import pytest

from app.domain.dwell_rule import DwellRule, Observation, Zone
from app.domain.text_chunking import chunk_text


def test_dwell_uses_video_time_and_emits_once():
    rule = DwellRule(Zone(x1=0, y1=0, x2=1, y2=1, dwell_seconds=2), max_gap=1.1)
    assert rule.feed(Observation(7, 0.5, 0.5, 0)) is False
    assert rule.feed(Observation(7, 0.5, 0.5, 1)) is False
    assert rule.feed(Observation(7, 0.5, 0.5, 2)) is True
    assert rule.feed(Observation(7, 0.5, 0.5, 3)) is False


def test_exit_and_tracking_gap_reset_timer():
    rule = DwellRule(Zone(x1=0, y1=0, x2=0.5, y2=1, dwell_seconds=2), max_gap=1.1)
    rule.feed(Observation(1, 0.2, 0.5, 0))
    rule.feed(Observation(1, 0.8, 0.5, 1))
    assert not rule.feed(Observation(1, 0.2, 0.5, 2))
    assert not rule.feed(Observation(1, 0.2, 0.5, 8))
    assert not rule.feed(Observation(1, 0.2, 0.5, 9))
    assert rule.feed(Observation(1, 0.2, 0.5, 10))


def test_zone_and_chunks_reject_invalid_inputs():
    with pytest.raises(ValueError):
        Zone(x1=0.8, y1=0, x2=0.2, y2=1)
    with pytest.raises(ValueError):
        chunk_text("hello", size=3, overlap=3)
    chunks = chunk_text("abcdefghij", size=5, overlap=1)
    assert chunks == ["abcde", "efghi", "ij"]
    assert chunk_text("   ") == []
