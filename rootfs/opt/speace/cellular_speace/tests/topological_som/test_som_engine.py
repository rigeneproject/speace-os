import pytest

from speace_core.cellular_brain.topological_som.som_engine import SOMEngine


def test_initialize_map():
    engine = SOMEngine(input_dim=4, grid_width=3, grid_height=3)
    assert len(engine.map) == 9
    assert len(engine.map[0].weights) == 4


def test_find_bmu():
    engine = SOMEngine(input_dim=2, grid_width=2, grid_height=2)
    # Manually set weights for predictable BMU
    engine.map[0].weights = [0.0, 0.0]
    engine.map[1].weights = [1.0, 1.0]
    engine.map[2].weights = [2.0, 2.0]
    engine.map[3].weights = [3.0, 3.0]
    bmu = engine.find_bmu([0.1, 0.1])
    assert bmu.grid_x == 0 and bmu.grid_y == 0


def test_update_changes_weights():
    engine = SOMEngine(input_dim=2, grid_width=2, grid_height=2, initial_learning_rate=0.5)
    engine.map[0].weights = [0.0, 0.0]
    engine.map[1].weights = [1.0, 1.0]
    engine.map[2].weights = [2.0, 2.0]
    engine.map[3].weights = [3.0, 3.0]
    sample = [0.1, 0.1]
    old_weights = [n.weights[:] for n in engine.map]
    engine.update(sample)
    assert engine.map[0].weights != old_weights[0]


def test_train_reduces_quantization_error():
    engine = SOMEngine(input_dim=2, grid_width=2, grid_height=2, initial_learning_rate=0.5)
    dataset = [
        [0.0, 0.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [1.0, 0.0],
    ]
    qe_before = engine.get_quantization_error(dataset)
    engine.train(dataset, epochs=5)
    qe_after = engine.get_quantization_error(dataset)
    assert qe_after < qe_before


def test_decay():
    engine = SOMEngine(
        input_dim=2,
        grid_width=2,
        grid_height=2,
        initial_learning_rate=0.5,
        initial_radius=2.0,
        lr_decay=0.9,
        radius_decay=0.9,
    )
    lr_before = engine.current_lr
    radius_before = engine.current_radius
    engine.update([0.0, 0.0])
    assert engine.current_lr < lr_before
    assert engine.current_radius < radius_before
