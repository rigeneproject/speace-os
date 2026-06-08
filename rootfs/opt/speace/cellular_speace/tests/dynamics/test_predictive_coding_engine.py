import numpy as np
import pytest

from speace_core.cellular_brain.dynamics.predictive_coding_engine import (
    PredictiveCodingEngine,
)


def test_register_layer():
    engine = PredictiveCodingEngine()
    engine.register_layer("s1", dim=4, level=0)
    assert "s1" in engine.layers
    assert engine.layers["s1"]["dim"] == 4
    assert engine.layers["s1"]["level"] == 0


def test_register_layer_invalid_level():
    engine = PredictiveCodingEngine()
    with pytest.raises(ValueError):
        engine.register_layer("x", dim=2, level=3)


def test_set_connection():
    engine = PredictiveCodingEngine()
    engine.register_layer("l0", dim=2, level=0)
    engine.register_layer("l1", dim=2, level=1)
    engine.set_connection("l1", "l0")
    assert "l1" in engine.weights["l0"]


def test_set_connection_unregistered():
    engine = PredictiveCodingEngine()
    with pytest.raises(ValueError):
        engine.set_connection("a", "b")


def test_predict():
    engine = PredictiveCodingEngine()
    engine.register_layer("sensory", dim=2, level=0)
    engine.register_layer("abstract", dim=2, level=2)
    engine.set_connection("abstract", "sensory")
    engine.layers["abstract"]["representation"] = np.array([1.0, 2.0])
    pred = engine.predict("sensory")
    expected = engine.weights["sensory"]["abstract"] @ np.array([1.0, 2.0])
    np.testing.assert_allclose(pred, expected)


def test_update():
    engine = PredictiveCodingEngine()
    engine.register_layer("s1", dim=3, level=0)
    engine.layers["s1"]["prediction"] = np.array([0.5, 0.5, 0.5])
    engine.update("s1", np.array([1.0, 1.0, 1.0]))
    assert engine.get_prediction_error("s1") == pytest.approx(1.5)
    # representation should move toward actual input
    np.testing.assert_allclose(
        engine.layers["s1"]["representation"],
        np.array([0.05, 0.05, 0.05]),
        atol=1e-6,
    )


def test_update_wrong_dim():
    engine = PredictiveCodingEngine()
    engine.register_layer("s1", dim=3, level=0)
    with pytest.raises(ValueError):
        engine.update("s1", np.array([1.0, 2.0]))


def test_get_prediction_error():
    engine = PredictiveCodingEngine()
    engine.register_layer("s1", dim=2, level=0)
    engine.layers["s1"]["prediction"] = np.array([0.0, 0.0])
    engine.update("s1", np.array([2.0, 3.0]))
    assert engine.get_prediction_error("s1") == pytest.approx(5.0)


def test_get_free_energy():
    engine = PredictiveCodingEngine()
    engine.register_layer("s1", dim=2, level=0)
    engine.layers["s1"]["prediction"] = np.array([0.0, 0.0])
    engine.update("s1", np.array([1.0, 2.0]))
    assert engine.get_free_energy() == pytest.approx(1.0 + 4.0)


def test_step_propagates_predictions_down():
    engine = PredictiveCodingEngine()
    engine.register_layer("sensory", dim=2, level=0)
    engine.register_layer("association", dim=2, level=1)
    engine.register_layer("abstract", dim=2, level=2)
    engine.set_connection("abstract", "association")
    engine.set_connection("association", "sensory")

    engine.layers["abstract"]["representation"] = np.array([4.0, 4.0])
    engine.layers["association"]["representation"] = np.array([4.0, 4.0])
    engine.layers["sensory"]["representation"] = np.array([0.0, 0.0])

    engine.step()

    # Predictions should have been generated for association and sensory
    assert not np.allclose(engine.layers["association"]["prediction"], np.zeros(2))
    assert not np.allclose(engine.layers["sensory"]["prediction"], np.zeros(2))


def test_step_propagates_errors_up():
    engine = PredictiveCodingEngine()
    engine.register_layer("sensory", dim=2, level=0)
    engine.register_layer("association", dim=2, level=1)
    engine.set_connection("association", "sensory")

    # Fix sensory representation as external input
    engine.update("sensory", np.array([2.0, 2.0]))
    # Give association a prediction so it has some state
    engine.layers["association"]["prediction"] = np.array([0.0, 0.0])
    engine.layers["association"]["representation"] = np.array([0.0, 0.0])

    prev_rep = engine.layers["association"]["representation"].copy()
    engine.step()
    # Association representation should update based on propagated error
    assert not np.allclose(engine.layers["association"]["representation"], prev_rep)


def test_step_updates_sensory_error_but_not_representation():
    engine = PredictiveCodingEngine()
    engine.register_layer("sensory", dim=2, level=0)
    engine.register_layer("association", dim=2, level=1)
    engine.set_connection("association", "sensory")

    engine.update("sensory", np.array([1.0, 1.0]))
    post_update_rep = engine.layers["sensory"]["representation"].copy()
    engine.layers["association"]["representation"] = np.array([2.0, 2.0])

    engine.step()

    # Sensory representation should remain unchanged by step()
    np.testing.assert_allclose(
        engine.layers["sensory"]["representation"], post_update_rep
    )
    # But prediction error should be recomputed using the new top-down prediction
    assert engine.layers["sensory"]["prediction_error"] is not None
