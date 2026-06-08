import pytest

from speace_core.cellular_brain.hopfield_krotov.hopfield_krotov_engine import (
    HopfieldKrotovEngine,
    HopfieldKrotovNeuronState,
)


def test_compute_hidden_activations():
    engine = HopfieldKrotovEngine(input_dim=3, hidden_dim=2)
    states = [
        HopfieldKrotovNeuronState(weights_in=[0.5, -0.2, 0.1], weights_out=[0.0, 0.0, 0.0]),
        HopfieldKrotovNeuronState(weights_in=[0.1, 0.4, -0.3], weights_out=[0.0, 0.0, 0.0]),
    ]
    inputs = [1.0, 2.0, 3.0]
    hidden = engine.compute_hidden_activations(states, inputs)
    assert len(hidden) == 2
    # With lateral inhibition, the strongest raw activation is suppressed less
    raw0 = 0.5 * 1.0 + (-0.2) * 2.0 + 0.1 * 3.0
    raw1 = 0.1 * 1.0 + 0.4 * 2.0 + (-0.3) * 3.0
    # inhibited = relu(raw - inhibition)
    assert hidden[0] == pytest.approx(max(0.0, raw0 - 0.5 * raw1), abs=1e-6)
    assert hidden[1] == pytest.approx(max(0.0, raw1 - 0.5 * raw0), abs=1e-6)


def test_compute_output():
    engine = HopfieldKrotovEngine(input_dim=3, hidden_dim=2)
    states = [
        HopfieldKrotovNeuronState(weights_in=[0.0, 0.0, 0.0], weights_out=[1.0, 0.0, 0.0]),
        HopfieldKrotovNeuronState(weights_in=[0.0, 0.0, 0.0], weights_out=[0.0, 1.0, 0.0]),
    ]
    hidden = [0.5, 0.8]
    output = engine.compute_output(states, hidden)
    assert output == pytest.approx([0.5, 0.8, 0.0], abs=1e-6)


def test_train_step_changes_weights():
    engine = HopfieldKrotovEngine(input_dim=2, hidden_dim=2, learning_rate=1.0)
    states = [
        HopfieldKrotovNeuronState(weights_in=[0.5, 0.5], weights_out=[0.1, 0.2]),
        HopfieldKrotovNeuronState(weights_in=[0.5, 0.5], weights_out=[0.3, -0.1]),
    ]
    inputs = [1.0, 2.0]
    new_states = engine.train_step(states, inputs)
    assert new_states[0].weights_in != states[0].weights_in
    assert new_states[0].weights_out != states[0].weights_out


def test_train_step_reconstruction():
    engine = HopfieldKrotovEngine(input_dim=2, hidden_dim=2, learning_rate=0.01)
    states = [
        HopfieldKrotovNeuronState(weights_in=[0.5, -0.2], weights_out=[0.1, 0.2]),
        HopfieldKrotovNeuronState(weights_in=[0.1, 0.4], weights_out=[0.3, -0.1]),
    ]
    inputs = [1.0, 2.0]
    hidden = engine.compute_hidden_activations(states, inputs)
    output = engine.compute_output(states, hidden)
    # Output should have same dimension as input
    assert len(output) == 2
