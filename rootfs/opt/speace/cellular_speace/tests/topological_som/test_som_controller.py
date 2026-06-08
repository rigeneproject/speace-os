import pytest

from speace_core.cellular_brain.topological_som.som_controller import SOMController


def test_train():
    ctrl = SOMController(input_dim=2, grid_width=2, grid_height=2)
    dataset = [
        [0.0, 0.0],
        [1.0, 1.0],
    ]
    result = ctrl.train(dataset, epochs=3)
    assert result.quantization_error >= 0.0
    assert len(result.final_map) == 4


def test_get_bmu_for():
    ctrl = SOMController(input_dim=2, grid_width=2, grid_height=2)
    ctrl.engine.map[0].weights = [0.0, 0.0]
    ctrl.engine.map[1].weights = [1.0, 1.0]
    ctrl.engine.map[2].weights = [2.0, 2.0]
    ctrl.engine.map[3].weights = [3.0, 3.0]
    bmu = ctrl.get_bmu_for([0.1, 0.1])
    assert bmu.grid_x == 0 and bmu.grid_y == 0
