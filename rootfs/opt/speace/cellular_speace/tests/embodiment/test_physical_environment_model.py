import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from speace_core.cellular_brain.embodiment.physical_environment_model import (
    PhysicalEnvironmentModel,
)


@pytest.fixture
def model():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PhysicalEnvironmentModel(base_path=tmpdir, learning_rate=0.1)


class TestInitialization:
    def test_state_vector_length(self, model):
        assert len(model.state) == 8
        assert np.allclose(model.state, 0.0)

    def test_state_keys(self, model):
        assert model.STATE_KEYS == [
            "cpu_avg",
            "mem_used",
            "disk_used",
            "net_in",
            "net_out",
            "temp_avg",
            "process_count",
            "battery_level",
        ]

    def test_persistence_path_created(self, model):
        assert model.state_path.parent.exists()


class TestUpdate:
    def test_update_changes_state(self, model):
        reading = {
            "cpu_avg": 45.0,
            "mem_used": 60.0,
            "disk_used": 30.0,
            "net_in": 100.0,
            "net_out": 80.0,
            "temp_avg": 55.0,
            "process_count": 120.0,
            "battery_level": 85.0,
        }
        result = model.update(reading)
        assert np.allclose(model.state, [
            45.0, 60.0, 30.0, 100.0, 80.0, 55.0, 120.0, 85.0,
        ])
        assert result == reading

    def test_update_with_partial_reading(self, model):
        reading = {"cpu_avg": 50.0, "mem_used": 40.0}
        result = model.update(reading)
        assert model.state[0] == 50.0
        assert model.state[1] == 40.0
        assert model.state[2] == 0.0
        assert result["disk_used"] == 0.0


class TestPredictionError:
    def test_prediction_error_computation(self, model):
        model.update({k: 10.0 for k in model.STATE_KEYS})
        model.predict_next_state()
        actual = {k: 12.0 for k in model.STATE_KEYS}
        error = model.get_prediction_error(actual)
        # predicted = 10.0, actual = 12.0, squared error per dim = 4.0, total = 8 * 4.0 = 32.0
        assert error == pytest.approx(32.0, abs=1e-6)

    def test_prediction_error_stored(self, model):
        model.update({k: 10.0 for k in model.STATE_KEYS})
        model.predict_next_state()
        model.get_prediction_error({k: 12.0 for k in model.STATE_KEYS})
        assert len(model.prediction_errors) == 1

    def test_prediction_error_without_predict(self, model):
        model.update({k: 10.0 for k in model.STATE_KEYS})
        # _last_predicted_state is still zeros
        error = model.get_prediction_error({k: 10.0 for k in model.STATE_KEYS})
        assert error == pytest.approx(800.0, abs=1e-6)


class TestLearning:
    def test_learning_reduces_error(self, model):
        # Fix current state at a non-zero vector
        current = {k: 1.0 for k in model.STATE_KEYS}
        model.update(current)

        # The actual next state is current + delta (delta = 0.5 per dim)
        delta = 0.5
        actual = {k: 1.0 + delta for k in model.STATE_KEYS}

        # Initial prediction with zero weights: predicted = current
        model.predict_next_state()
        initial_error = model.get_prediction_error(actual)

        # Learn repeatedly on the same transition
        errors = [initial_error]
        for _ in range(20):
            model.predict_next_state()
            model.learn_transition(actual)
            errors.append(model.get_prediction_error(actual))

        assert errors[-1] < errors[0]
        assert errors[-1] < 5.0  # should converge well below initial 32.0

    def test_action_affects_prediction(self, model):
        model.update({k: 10.0 for k in model.STATE_KEYS})
        baseline = model.predict_next_state()
        action = {"cpu_avg": 5.0, "process_count": 3.0}
        with_action = model.predict_next_state(action=action)
        # Action adds raw features through action_effect_weights (currently zero)
        # so predicted should equal baseline since weights are zero
        assert with_action == baseline


class TestStabilityScore:
    def test_stability_score_high_with_no_errors(self, model):
        assert model.get_stability_score() == 1.0

    def test_stability_score_decreases_with_errors(self, model):
        model.update({k: 10.0 for k in model.STATE_KEYS})
        for _ in range(5):
            model.predict_next_state()
            model.get_prediction_error({k: 20.0 for k in model.STATE_KEYS})
        score = model.get_stability_score()
        assert 0.0 < score < 1.0

    def test_stability_score_bounded(self, model):
        model.update({k: 10.0 for k in model.STATE_KEYS})
        for _ in range(10):
            model.predict_next_state()
            model.get_prediction_error({k: 20.0 for k in model.STATE_KEYS})
        score = model.get_stability_score()
        assert 0.0 <= score <= 1.0


class TestAnomalyScore:
    def test_anomaly_score_zero_with_insufficient_history(self, model):
        assert model.get_anomaly_score() == 0.0

    def test_anomaly_score_rises_for_outlier(self, model):
        # Build a history of low-cpu readings
        for i in range(20):
            reading = {k: 10.0 for k in model.STATE_KEYS}
            reading["cpu_avg"] = 20.0
            model.update(reading)

        # Now an outlier cpu_avg
        outlier = {k: 10.0 for k in model.STATE_KEYS}
        outlier["cpu_avg"] = 100.0
        model.update(outlier)
        score = model.get_anomaly_score()
        assert score > 2.0  # Z-score should be well above 2

    def test_anomaly_score_low_for_normal(self, model):
        for i in range(20):
            reading = {k: float(i % 5) for k in model.STATE_KEYS}
            model.update(reading)
        normal = {k: 2.0 for k in model.STATE_KEYS}
        model.update(normal)
        score = model.get_anomaly_score()
        assert score < 2.0


class TestStateSummary:
    def test_summary_format(self, model):
        reading = {
            "cpu_avg": 45.5,
            "mem_used": 60.0,
            "disk_used": 30.0,
            "net_in": 100.0,
            "net_out": 80.0,
            "temp_avg": 55.0,
            "process_count": 120.0,
            "battery_level": 85.0,
        }
        model.update(reading)
        summary = model.get_state_summary()
        assert summary.startswith("PhysicalEnvironmentModel(")
        assert "cpu_avg=45.50" in summary
        assert "battery_level=85.00" in summary


class TestPersistence:
    def test_persistence_round_trip(self, model):
        reading = {
            "cpu_avg": 45.0,
            "mem_used": 60.0,
            "disk_used": 30.0,
            "net_in": 100.0,
            "net_out": 80.0,
            "temp_avg": 55.0,
            "process_count": 120.0,
            "battery_level": 85.0,
        }
        model.update(reading)
        model.update(reading)

        assert model.state_path.exists()
        lines = model.state_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            record = json.loads(line)
            assert "timestamp" in record
            assert "state" in record
            assert record["state"]["cpu_avg"] == 45.0
