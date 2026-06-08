import pytest

from speace_core.cellular_brain.bcm_selectivity.bcm_selectivity_engine import (
    BCMNeuronState,
    BCMSelectivityEngine,
)


def test_compute_activation():
    engine = BCMSelectivityEngine()
    weights = [0.5, -0.2, 0.1]
    inputs = [1.0, 2.0, 3.0]
    y = engine.compute_activation(weights, inputs)
    assert y == pytest.approx(0.5 * 1.0 + (-0.2) * 2.0 + 0.1 * 3.0)


def test_update_threshold():
    engine = BCMSelectivityEngine(theta_decay=0.9)
    state = BCMNeuronState(weights=[1.0], theta_m=0.5)
    new_theta = engine.update_threshold(state, activation=2.0)
    expected = 0.9 * 0.5 + 0.1 * 4.0
    assert new_theta == pytest.approx(expected)


def test_compute_weight_update_ltp():
    engine = BCMSelectivityEngine(learning_rate=0.1)
    weights = [0.0, 0.0]
    inputs = [1.0, 2.0]
    activation = 2.0
    theta_m = 1.0
    dw = engine.compute_weight_update(weights, inputs, activation, theta_m)
    factor = 0.1 * 2.0 * (2.0 - 1.0)
    assert dw == pytest.approx([factor * 1.0, factor * 2.0])


def test_compute_weight_update_ltd():
    engine = BCMSelectivityEngine(learning_rate=0.1)
    weights = [0.0, 0.0]
    inputs = [1.0, 2.0]
    activation = 0.5
    theta_m = 1.0
    dw = engine.compute_weight_update(weights, inputs, activation, theta_m)
    factor = 0.1 * 0.5 * (0.5 - 1.0)
    assert dw == pytest.approx([factor * 1.0, factor * 2.0])


def test_update_neuron_changes_weights():
    engine = BCMSelectivityEngine(learning_rate=0.1)
    state = BCMNeuronState(weights=[0.5, -0.2], theta_m=0.0, activation_history=[])
    new_state = engine.update_neuron(state, inputs=[1.0, 2.0])
    assert new_state.weights != [0.5, -0.2]
    assert new_state.theta_m > 0.0
    assert len(new_state.activation_history) == 1


def test_train_neuron_multiple_steps():
    engine = BCMSelectivityEngine(learning_rate=0.01)
    state = BCMNeuronState(weights=[0.0, 0.0], theta_m=0.0, activation_history=[])
    trained = engine.train_neuron(state, inputs=[1.0, -1.0], steps=10)
    assert len(trained.activation_history) == 10
    assert trained.selectivity_index >= 0.0
