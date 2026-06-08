import pytest

from speace_core.cellular_brain.identity_kernel.ontogenetic_stage_tracker import (
    OntogeneticStageTracker,
)


class FakeMetrics:
    coherence_phi = 0.8
    tick = 200


def test_stage_transition_ready():
    tracker = OntogeneticStageTracker(current_stage="stage_0")
    result = tracker.evaluate_stage_transition(
        metrics=FakeMetrics(),
        capabilities=[],
        clone_count=1,
    )
    assert result.transition_ready is True
    assert result.next_stage == "stage_1"


def test_stage_transition_blocked_by_stability():
    tracker = OntogeneticStageTracker(current_stage="stage_0")
    result = tracker.evaluate_stage_transition(
        metrics={"coherence_phi": 0.3, "tick": 200},
        capabilities=[],
        clone_count=1,
    )
    assert result.transition_ready is False
    assert any("stability_too_low" in b for b in result.blockers)


def test_stage_transition_blocked_by_missing_capability():
    tracker = OntogeneticStageTracker(current_stage="stage_1")
    result = tracker.evaluate_stage_transition(
        metrics={"coherence_phi": 0.8, "tick": 200},
        capabilities=[],
        clone_count=1,
    )
    assert result.transition_ready is False
    assert any("missing_capability" in b for b in result.blockers)


def test_stage_transition_blocked_by_clones():
    tracker = OntogeneticStageTracker(current_stage="stage_3")
    result = tracker.evaluate_stage_transition(
        metrics={"coherence_phi": 0.85, "tick": 400},
        capabilities=["clone_safety"],
        clone_count=1,
    )
    assert result.transition_ready is False
    assert "insufficient_clones" in result.blockers


def test_advance_stage():
    tracker = OntogeneticStageTracker(current_stage="stage_0")
    tracker.advance_stage()
    assert tracker.current_stage == "stage_1"


def test_max_stage_reached():
    tracker = OntogeneticStageTracker(current_stage="stage_7")
    result = tracker.evaluate_stage_transition(
        metrics=FakeMetrics(),
        capabilities=[],
        clone_count=1,
    )
    assert result.transition_ready is False
    assert "max_stage_reached" in result.blockers
