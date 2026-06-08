import pytest

from speace_core.cellular_brain.hopfield_krotov.hopfield_krotov_controller import (
    HopfieldKrotovController,
)


def test_initialize_population():
    ctrl = HopfieldKrotovController(input_dim=4, hidden_dim=3)
    states = ctrl.initialize_population()
    assert len(states) == 3
    assert len(states[0].weights_in) == 4
    assert len(states[0].weights_out) == 4


def test_train():
    ctrl = HopfieldKrotovController(input_dim=4, hidden_dim=3)
    states = ctrl.initialize_population()
    dataset = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]
    result = ctrl.train(states, dataset, epochs=2)
    assert len(result.final_states) == 3
    assert result.mean_reconstruction_error >= 0.0
