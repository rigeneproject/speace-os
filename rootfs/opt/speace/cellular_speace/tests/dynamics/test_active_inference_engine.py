import math

import pytest

from speace_core.cellular_brain.dynamics.active_inference_engine import (
    ActiveInferenceEngine,
)


def test_register_state():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.5)
    assert engine.priors["s1"] == 0.5
    assert engine.beliefs["s1"] == 0.5


def test_register_state_invalid_probability():
    engine = ActiveInferenceEngine()
    with pytest.raises(ValueError):
        engine.register_state("s1", 1.5)


def test_register_action():
    engine = ActiveInferenceEngine()
    engine.register_action("a1", {"s1": 0.7, "s2": 0.3})
    assert engine.actions["a1"]["s1"] == pytest.approx(0.7)


def test_register_action_invalid_sum():
    engine = ActiveInferenceEngine()
    with pytest.raises(ValueError):
        engine.register_action("a1", {"s1": 0.5, "s2": 0.3})


def test_observe_updates_beliefs():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.5)
    engine.register_state("s2", 0.5)
    engine.observe("s1", likelihood=2.0)
    # belief in s1 should increase relative to s2
    assert engine.beliefs["s1"] > engine.beliefs["s2"]


def test_observe_unregistered_state():
    engine = ActiveInferenceEngine()
    with pytest.raises(ValueError):
        engine.observe("s1", likelihood=0.5)


def test_observe_zero_likelihood_eliminates_state():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.6)
    engine.register_state("s2", 0.4)
    engine.observe("s1", likelihood=0.0)
    # s1 becomes impossible, so all belief shifts to s2
    assert engine.beliefs["s1"] == pytest.approx(0.0)
    assert engine.beliefs["s2"] == pytest.approx(1.0)


def test_observe_zero_likelihood_falls_back_to_priors():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.6)
    engine.observe("s1", likelihood=0.0)
    # total becomes 0, so beliefs fall back to priors and renormalize to 1.0
    assert engine.beliefs["s1"] == pytest.approx(1.0)


def test_expected_free_energy_basic():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.5)
    engine.register_state("s2", 0.5)
    # Action with deterministic outcome to s1
    engine.register_action("a1", {"s1": 1.0, "s2": 0.0})
    efe = engine.expected_free_energy("a1")
    # deterministic -> low expected surprise, but epistemic value is
    # KL(1.0||0.5) = log(2) ~0.693. EFE = 0 - 0.693 = -0.693
    assert efe < 0


def test_expected_free_energy_vs_certainty():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.5)
    engine.register_state("s2", 0.5)
    engine.register_action("a1", {"s1": 0.5, "s2": 0.5})  # uncertain
    engine.register_action("a2", {"s1": 1.0, "s2": 0.0})  # certain
    efe_uncertain = engine.expected_free_energy("a1")
    efe_certain = engine.expected_free_energy("a2")
    # The certain action should have lower EFE because it minimises surprise
    # and provides information gain (negative contribution).
    assert efe_certain < efe_uncertain


def test_select_action():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.8)
    engine.register_state("s2", 0.2)
    engine.register_action("a1", {"s1": 0.5, "s2": 0.5})
    engine.register_action("a2", {"s1": 1.0, "s2": 0.0})
    best = engine.select_action()
    # a2 is deterministic and aligns with the more likely state, so lower EFE
    assert best == "a2"


def test_select_action_no_actions():
    engine = ActiveInferenceEngine()
    assert engine.select_action() is None


def test_step_returns_action_and_updates_beliefs():
    engine = ActiveInferenceEngine()
    engine.register_state("s1", 0.5)
    engine.register_state("s2", 0.5)
    engine.register_action("a1", {"s1": 1.0, "s2": 0.0})
    engine.register_action("a2", {"s1": 0.0, "s2": 1.0})
    chosen = engine.step()
    assert chosen in ("a1", "a2")
    # Beliefs should now match the outcome distribution of the chosen action
    dist = engine.actions[chosen]
    for state_id, prob in dist.items():
        assert engine.beliefs[state_id] == pytest.approx(prob)
