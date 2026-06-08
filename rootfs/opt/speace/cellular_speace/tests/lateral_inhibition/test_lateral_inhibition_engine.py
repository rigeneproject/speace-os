import pytest

from speace_core.cellular_brain.lateral_inhibition.lateral_inhibition_engine import (
    LateralInhibitionEngine,
)


def test_apply_basic():
    engine = LateralInhibitionEngine(inhibition_strength=0.5)
    raw = [1.0, 0.8, 0.2]
    state = engine.apply(raw)
    assert len(state.inhibited_activations) == 3
    # Strongest neuron (index 0) receives less total inhibition than it exerts
    # but its own activation is raw - sum(others * strength)
    assert state.inhibited_activations[0] < raw[0]


def test_apply_local_radius():
    engine = LateralInhibitionEngine(inhibition_strength=0.5, local_radius=1)
    raw = [1.0, 0.8, 0.2, 0.1]
    state = engine.apply(raw)
    assert len(state.inhibited_activations) == 4
    # Neuron 0 is inhibited only by neuron 1 (radius 1)
    expected_inhibition = 0.5 * (1.0 - 1 / 2) * 0.8
    assert state.inhibited_activations[0] == pytest.approx(1.0 - expected_inhibition, rel=1e-3)


def test_apply_with_custom_matrix():
    matrix = [
        [0.0, 0.2, 0.0],
        [0.2, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ]
    engine = LateralInhibitionEngine(inhibition_matrix=matrix)
    raw = [1.0, 1.0, 1.0]
    state = engine.apply(raw)
    assert state.inhibited_activations[0] == pytest.approx(0.8)
    assert state.inhibited_activations[1] == pytest.approx(0.8)
    assert state.inhibited_activations[2] == pytest.approx(1.0)


def test_apply_and_normalize():
    engine = LateralInhibitionEngine(inhibition_strength=0.5)
    raw = [2.0, 1.0, 0.5]
    state = engine.apply_and_normalize(raw, normalize=True)
    max_val = max(abs(a) for a in state.inhibited_activations)
    assert max_val == pytest.approx(1.0)


def test_apply_no_negative_if_softmax():
    engine = LateralInhibitionEngine(
        inhibition_strength=0.9, use_softmax_competition=True
    )
    raw = [0.5, 0.5, 0.5]
    state = engine.apply(raw)
    assert all(a >= 0.0 for a in state.inhibited_activations)
