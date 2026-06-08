"""Tests for SimulatedEnvironmentEngine — Phase 2 Simulated Embodiment."""

import os
import tempfile

import pytest

from speace_core.cellular_brain.embodiment.cyber_physical_sensor_array import (
    CyberPhysicalSensorArray,
)
from speace_core.cellular_brain.embodiment.digital_twin_model import DigitalTwinModel
from speace_core.cellular_brain.embodiment.physical_environment_model import (
    PhysicalEnvironmentModel,
)
from speace_core.cellular_brain.embodiment.simulated_environment_engine import (
    SimulatedEnvironmentEngine,
)


@pytest.fixture
def engine():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        sensor_array = CyberPhysicalSensorArray(history_size=10)
        env_model = PhysicalEnvironmentModel(base_path=tmpdir)
        twin = DigitalTwinModel(sensor_array=sensor_array, environment_model=env_model, data_root=tmpdir)
        se = SimulatedEnvironmentEngine(digital_twin=twin, data_root=tmpdir)
        yield se
        sensor_array.stop_continuous_sampling()


class TestSimulatedEnvironmentEngine:
    def test_run_experiment_unknown_type(self, engine):
        result = engine.run_experiment("unknown")
        assert result.get("error") == "unknown_experiment_type"

    def test_run_experiment_pressure(self, engine):
        result = engine.run_experiment("pressure")
        assert "experiment_id" in result
        assert result["experiment_type"] == "pressure"
        assert "consequences" in result
        assert "safe" in result

    def test_run_batch(self, engine):
        results = engine.run_batch(count=2)
        assert len(results) == 2

    def test_list_experiments(self, engine):
        engine.run_experiment("pressure")
        exps = engine.list_experiments(limit=10)
        assert len(exps) == 1

    def test_summary(self, engine):
        engine.run_experiment("pressure")
        s = engine.summary()
        assert s["total_experiments"] == 1
        assert s["by_type"]["pressure"] == 1
