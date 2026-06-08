import pytest

from speace_core.cellular_brain.bcm_selectivity.bcm_selectivity_controller import (
    BCMSelectivityController,
)


def test_initialize_neurons():
    ctrl = BCMSelectivityController(input_dim=10)
    states = ctrl.initialize_neurons(count=5)
    assert len(states) == 5
    assert len(states[0].weights) == 10


def test_train_population():
    ctrl = BCMSelectivityController(input_dim=4)
    states = ctrl.initialize_neurons(count=3)
    dataset = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]
    result = ctrl.train_population(states, dataset, epochs=2)
    assert len(result.final_states) == 3
    assert result.mean_selectivity >= 0.0
    assert result.selectivity_diversity >= 0.0


def test_compute_population_response():
    ctrl = BCMSelectivityController(input_dim=3)
    states = ctrl.initialize_neurons(count=2)
    inputs = [1.0, 2.0, 3.0]
    responses = ctrl.compute_population_response(states, inputs)
    assert len(responses) == 2
    assert all(isinstance(r, float) for r in responses)
