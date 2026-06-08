"""Tests for T127 — MetacognitiveMonitor heuristics."""

import time

import pytest

from speace_core.cellular_brain.metacognition.metacognitive_monitor import MetacognitiveMonitor


def _make_state(
    *,
    chaos_score: float = 0.3,
    rigidity_score: float = 0.2,
    drift: float = 0.1,
    coherence_phi: float = 0.7,
    pending_proposals: int = 0,
    health_score: float = 0.8,
    divergence_detected: bool = False,
    action_tendency: str = "explore",
    pending_patches: int = 0,
    intervention_count: int = 0,
) -> dict:
    return {
        "dynamics": {
            "chaos_score": chaos_score,
            "rigidity_score": rigidity_score,
            "drift": drift,
            "stabilizer": {"intervention_count": intervention_count},
        },
        "cognition": {
            "self_model": {"coherence_phi": coherence_phi},
        },
        "alert_engine": {
            "regulation_proposals": {"pending_count": pending_proposals},
            "health_score": health_score,
            "alerts": [],
        },
        "identity": {"divergence_detected": divergence_detected},
        "drives": {
            "drives": [
                {"urgency": 0.5, "name": "explore"},
                {"urgency": 0.3, "name": "stability"},
            ],
            "action_tendency": action_tendency,
        },
        "safety": {"pending_patches": pending_patches},
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# Observation
# ------------------------------------------------------------------ #


def test_observe_stable_workspace():
    monitor = MetacognitiveMonitor()
    state = _make_state(chaos_score=0.1, rigidity_score=0.1, coherence_phi=0.9)
    obs = monitor.observe(state)
    assert obs.workspace_stability > 0.8


def test_observe_unstable_workspace():
    monitor = MetacognitiveMonitor()
    state = _make_state(chaos_score=0.9, rigidity_score=0.9, coherence_phi=0.1)
    obs = monitor.observe(state)
    assert obs.workspace_stability < 0.4


def test_observe_regulation_density():
    monitor = MetacognitiveMonitor()
    state = _make_state(pending_proposals=10, health_score=0.2)
    obs = monitor.observe(state)
    assert obs.regulation_density > 0.0


# ------------------------------------------------------------------ #
# Error detection
# ------------------------------------------------------------------ #


def test_detect_contradiction_chaos_and_rigidity():
    monitor = MetacognitiveMonitor()
    state = _make_state()
    state["alert_engine"]["alerts"] = [
        {"alert_type": "chaos_warning"},
        {"alert_type": "rigidity_warning"},
    ]
    errs = monitor.detect_errors(state)
    assert errs.contradiction is True


def test_detect_similarity_collapse():
    monitor = MetacognitiveMonitor()
    state = _make_state(divergence_detected=True)
    errs = monitor.detect_errors(state)
    assert errs.similarity_collapse is True


def test_detect_memory_saturation():
    monitor = MetacognitiveMonitor()
    state = _make_state(pending_patches=10)
    errs = monitor.detect_errors(state)
    assert errs.memory_saturation is True


def test_detect_overfocus():
    monitor = MetacognitiveMonitor()
    state = _make_state(chaos_score=0.1)
    state["drives"]["drives"] = [{"urgency": 0.9, "name": "explore"}]
    errs = monitor.detect_errors(state)
    assert errs.overfocus is True


# ------------------------------------------------------------------ #
# Meta-state classification
# ------------------------------------------------------------------ #


def test_classify_stable():
    monitor = MetacognitiveMonitor()
    state = _make_state(chaos_score=0.1, coherence_phi=0.9)
    meta = monitor.generate_meta_state(state)
    assert meta.meta_state_label == "stable"


def test_classify_unstable():
    monitor = MetacognitiveMonitor()
    state = _make_state(chaos_score=0.8, coherence_phi=0.2)
    state["alert_engine"]["alerts"] = [{"alert_type": "chaos_warning"}]
    meta = monitor.generate_meta_state(state)
    assert meta.meta_state_label == "unstable"


# ------------------------------------------------------------------ #
# Reflective narrative
# ------------------------------------------------------------------ #


def test_reflective_narrative_contains_errors():
    monitor = MetacognitiveMonitor()
    state = _make_state(divergence_detected=True, pending_patches=10)
    state["alert_engine"]["alerts"] = [{"alert_type": "chaos_warning"}, {"alert_type": "rigidity_warning"}]
    meta = monitor.generate_meta_state(state)
    assert "collapse" in meta.reflective_narrative or "Contradictory" in meta.reflective_narrative


# ------------------------------------------------------------------ #
# Epistemic confidence
# ------------------------------------------------------------------ #


def test_attach_confidence_fallback():
    monitor = MetacognitiveMonitor()
    state = _make_state()
    conf = monitor.attach_confidence(state)
    assert 0.0 <= conf.confidence_score <= 1.0
    assert 0.0 <= conf.uncertainty_score <= 1.0


# ------------------------------------------------------------------ #
# Strategy evaluation
# ------------------------------------------------------------------ #


def test_evaluate_strategy_improved():
    monitor = MetacognitiveMonitor()
    pre = _make_state(health_score=0.3)
    post = _make_state(health_score=0.9)
    eval_ = monitor.evaluate_strategy(pre, post, regulation_id="RP-1")
    assert eval_.improved is True
    assert eval_.delta > 0.05


def test_evaluate_strategy_not_improved():
    monitor = MetacognitiveMonitor()
    pre = _make_state(health_score=0.8)
    post = _make_state(health_score=0.82)
    eval_ = monitor.evaluate_strategy(pre, post, regulation_id="RP-2")
    assert eval_.improved is False
