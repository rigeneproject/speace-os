import numpy as np
import pytest

from speace_core.cellular_brain.regulation.cognitive_attractor_tracker import (
    AttractorEscape,
    CognitiveAttractorTracker,
)


@pytest.fixture
def tracker():
    return CognitiveAttractorTracker(
        history_window=200,
        attractor_radius=0.2,
        min_visit_count=3,
    )


# ---------------------------------------------------------------------------
# Basic initialization
# ---------------------------------------------------------------------------

def test_init_defaults():
    t = CognitiveAttractorTracker()
    assert t.history_window == 500
    assert t.attractor_radius == 0.15
    assert t.min_visit_count == 5


def test_init_custom(tracker):
    assert tracker.history_window == 200
    assert tracker.attractor_radius == 0.2
    assert tracker.min_visit_count == 3


# ---------------------------------------------------------------------------
# record_state
# ---------------------------------------------------------------------------

def test_record_state_increments_tick(tracker):
    tracker.record_state([0.1, 0.2])
    assert tracker._tick == 1
    tracker.record_state([0.2, 0.3])
    assert tracker._tick == 2


def test_record_state_stores_history(tracker):
    tracker.record_state([1.0, 0.0])
    tracker.record_state([0.0, 1.0])
    history = tracker.get_state_history()
    assert len(history) == 2


# ---------------------------------------------------------------------------
# detect_attractor
# ---------------------------------------------------------------------------

def test_detect_attractor_none_on_empty(tracker):
    assert tracker.detect_attractor() is None


def test_detect_attractor_after_visits(tracker):
    center = np.array([0.5, 0.5])
    for _ in range(5):
        tracker.record_state(center.tolist())
    # First visit creates attractor, subsequent visits build count
    # Need enough visits for min_visit_count
    assert tracker.detect_attractor() is not None


def test_detect_attractor_returns_id(tracker):
    for _ in range(10):
        tracker.record_state([0.1, 0.1])
    aid = tracker.detect_attractor()
    assert isinstance(aid, int)
    assert aid >= 0


# ---------------------------------------------------------------------------
# measure_attractor_stability
# ---------------------------------------------------------------------------

def test_measure_stability_zero_on_empty(tracker):
    assert tracker.measure_attractor_stability() == 0.0


def test_measure_stability_high_when_trapped(tracker):
    for _ in range(20):
        tracker.record_state([0.5, 0.5])
    stability = tracker.measure_attractor_stability()
    assert stability > 0.8


def test_measure_stability_low_when_wandering(tracker):
    for i in range(20):
        tracker.record_state([i * 0.1, i * 0.1])
    assert tracker.measure_attractor_stability() < 0.5


# ---------------------------------------------------------------------------
# get_attractor_count
# ---------------------------------------------------------------------------

def test_get_attractor_count_zero_initially(tracker):
    assert tracker.get_attractor_count() == 0


def test_get_attractor_count_one(tracker):
    for _ in range(10):
        tracker.record_state([0.1, 0.1])
    assert tracker.get_attractor_count() >= 1


def test_get_attractor_count_multiple(tracker):
    for _ in range(5):
        tracker.record_state([0.1, 0.1])
    for _ in range(5):
        tracker.record_state([0.9, 0.9])
    assert tracker.get_attractor_count() >= 2


# ---------------------------------------------------------------------------
# get_escape_history
# ---------------------------------------------------------------------------

def test_escape_history_empty_initially(tracker):
    assert tracker.get_escape_history() == []


def test_escape_history_records_transition(tracker):
    for _ in range(5):
        tracker.record_state([0.1, 0.1])
    for _ in range(5):
        tracker.record_state([0.9, 0.9])
    history = tracker.get_escape_history()
    assert len(history) >= 1
    assert "from_attractor_id" in history[0]
    assert "to_attractor_id" in history[0]


def test_escape_history_tick_increments(tracker):
    for _ in range(5):
        tracker.record_state([0.1, 0.1])
    for _ in range(5):
        tracker.record_state([0.9, 0.9])
    history = tracker.get_escape_history()
    assert history[0]["tick"] > 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persist_creates_file(tmp_path):
    log_path = tmp_path / "attractor.jsonl"
    t = CognitiveAttractorTracker(persistence_log_path=str(log_path))
    t.record_state([0.1, 0.2])
    t.persist()
    assert log_path.exists()
    content = log_path.read_text()
    assert "attractor_count" in content


def test_persist_appends(tmp_path):
    log_path = tmp_path / "attractor.jsonl"
    t = CognitiveAttractorTracker(persistence_log_path=str(log_path))
    t.record_state([0.1, 0.2])
    t.persist()
    t.persist()
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 2
