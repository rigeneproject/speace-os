"""Tests for DigitalTwinModel — Phase 2 Simulated Embodiment."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.embodiment.cyber_physical_sensor_array import (
    CyberPhysicalSensorArray,
)
from speace_core.cellular_brain.embodiment.digital_twin_model import DigitalTwinModel
from speace_core.cellular_brain.embodiment.physical_environment_model import (
    PhysicalEnvironmentModel,
)


@pytest.fixture
def twin():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        sensor_array = CyberPhysicalSensorArray(history_size=10)
        env_model = PhysicalEnvironmentModel(base_path=tmpdir)
        dt = DigitalTwinModel(sensor_array=sensor_array, environment_model=env_model, data_root=tmpdir)
        yield dt
        sensor_array.stop_continuous_sampling()


class TestDigitalTwinModel:
    def test_observe_returns_snapshot(self, twin):
        state = twin.observe()
        assert "timestamp" in state
        assert "sensor_snapshot" in state
        assert "environment_state" in state
        assert "predicted_next" in state
        assert "stability_score" in state
        assert "anomaly_score" in state

    def test_simulate_action(self, twin):
        twin.observe()
        sim = twin.simulate_action({"cpu_avg": 20.0}, horizon_ticks=3)
        assert sim["action"] == {"cpu_avg": 20.0}
        assert len(sim["trace"]) == 3
        assert "changes" in sim
        assert "primary_effects" in sim

    def test_record_and_get_hypotheses(self, twin):
        twin.record_hypothesis("cpu_spike", "temperature_rise", 0.7)
        h = twin.get_hypotheses(limit=10)
        assert len(h) == 1
        assert h[0]["cause"] == "cpu_spike"
        assert h[0]["effect"] == "temperature_rise"

    def test_infer_hypotheses_from_delta_empty(self, twin):
        # No delta yet
        h = twin.infer_hypotheses_from_delta()
        assert h == []

    def test_summary(self, twin):
        s = twin.summary()
        assert "has_snapshot" in s
        assert "stability_latest" in s
        assert "hypothesis_count" in s
