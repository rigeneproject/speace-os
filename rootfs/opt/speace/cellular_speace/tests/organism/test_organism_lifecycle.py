import pytest

from speace_core.cellular_brain.organism import OrganismLifecycleManager, OrganismLifecycleState


def test_lifecycle_valid_transition():
    mgr = OrganismLifecycleManager(OrganismLifecycleState.INITIALIZING.value)
    assert mgr.validate_transition(OrganismLifecycleState.BASELINE.value) is True
    assert mgr.transition_to(OrganismLifecycleState.BASELINE.value) is True
    assert mgr.current_state == OrganismLifecycleState.BASELINE.value


def test_lifecycle_invalid_transition_blocked():
    mgr = OrganismLifecycleManager(OrganismLifecycleState.ACTIVE.value)
    assert mgr.validate_transition(OrganismLifecycleState.INITIALIZING.value) is False
    assert mgr.transition_to(OrganismLifecycleState.INITIALIZING.value) is False


def test_lifecycle_classify_critical():
    mgr = OrganismLifecycleManager()
    state = mgr.classify_lifecycle_state(health_score=0.1, metabolic_mode="normal", safety_risk=0.0)
    assert state == OrganismLifecycleState.CRITICAL.value


def test_lifecycle_classify_active():
    mgr = OrganismLifecycleManager()
    state = mgr.classify_lifecycle_state(health_score=0.9, metabolic_mode="normal", safety_risk=0.0)
    assert state == OrganismLifecycleState.ACTIVE.value


def test_lifecycle_classify_conservation():
    mgr = OrganismLifecycleManager()
    state = mgr.classify_lifecycle_state(health_score=0.7, metabolic_mode="conservation", safety_risk=0.0)
    assert state == OrganismLifecycleState.CONSERVATION.value


def test_lifecycle_classify_recovery():
    mgr = OrganismLifecycleManager()
    state = mgr.classify_lifecycle_state(health_score=0.7, metabolic_mode="normal", safety_risk=0.5)
    assert state == OrganismLifecycleState.RECOVERY.value


def test_lifecycle_snapshot():
    mgr = OrganismLifecycleManager(OrganismLifecycleState.BASELINE.value)
    mgr.transition_to(OrganismLifecycleState.ACTIVE.value)
    snap = mgr.snapshot()
    assert snap["current_state"] == OrganismLifecycleState.ACTIVE.value
    assert len(snap["transition_history"]) == 1


def test_lifecycle_transition_history():
    mgr = OrganismLifecycleManager(OrganismLifecycleState.INITIALIZING.value)
    mgr.transition_to(OrganismLifecycleState.BASELINE.value)
    mgr.transition_to(OrganismLifecycleState.ACTIVE.value)
    assert len(mgr._history) == 2
