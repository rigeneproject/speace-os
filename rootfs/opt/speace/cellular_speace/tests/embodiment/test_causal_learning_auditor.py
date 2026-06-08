"""Tests for CausalLearningAuditor — T150."""

import json
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.embodiment.causal_learning_auditor import (
    CausalLearningAuditor,
)
from speace_core.cellular_brain.embodiment.cyber_physical_sensor_array import (
    CyberPhysicalSensorArray,
)
from speace_core.cellular_brain.embodiment.digital_twin_model import DigitalTwinModel
from speace_core.cellular_brain.embodiment.physical_environment_model import (
    PhysicalEnvironmentModel,
)


@pytest.fixture
def auditor():
    with tempfile.TemporaryDirectory() as tmpdir:
        sensor_array = CyberPhysicalSensorArray(history_size=10)
        env_model = PhysicalEnvironmentModel(base_path=tmpdir)
        twin = DigitalTwinModel(sensor_array=sensor_array, environment_model=env_model, data_root=tmpdir)
        a = CausalLearningAuditor(digital_twin=twin, data_root=tmpdir)
        yield a
        sensor_array.stop_continuous_sampling()


class TestCausalLearningAuditor:
    def test_audit_action_simulated_only(self, auditor):
        def dummy_execute():
            return {"success": True, "result": "ok"}

        report = auditor.audit_action(
            action_name="test_action",
            action_params={"x": 1},
            execute_fn=dummy_execute,
            simulate_only=True,
        )
        assert report["run_id"].startswith("causal_")
        assert report["action"]["simulated_only"] is True
        assert report["action"]["success"] is True
        assert "pre_state_summary" in report
        assert "post_state_summary" in report
        assert "hypotheses" in report
        assert "aggregate_confidence" in report

    def test_audit_action_real_marks_not_simulated(self, auditor):
        def dummy_execute():
            return {"success": True, "result": "done"}

        report = auditor.audit_action(
            action_name="real_action",
            action_params={},
            execute_fn=dummy_execute,
            simulate_only=False,
        )
        assert report["action"]["simulated_only"] is False

    def test_persistence(self, auditor):
        def dummy_execute():
            return {"success": True, "result": "ok"}

        auditor.audit_action("act", {}, dummy_execute, simulate_only=True)
        reports = auditor.get_reports()
        assert len(reports) == 1
        assert reports[0]["action"]["name"] == "act"

    def test_summary(self, auditor):
        def dummy_execute():
            return {"success": True, "result": "ok"}

        for _ in range(3):
            auditor.audit_action("act", {}, dummy_execute, simulate_only=True)
        summary = auditor.summary()
        assert summary["total_audits"] == 3
        assert summary["successful_audits"] == 3
        assert summary["simulated_only"] == 3
        assert summary["real_actions"] == 0

    def test_audit_action_with_failed_execute(self, auditor):
        def fail_execute():
            return {"success": False, "error": "boom"}

        report = auditor.audit_action("fail", {}, fail_execute)
        assert report["action"]["success"] is False
        assert "aggregate_confidence" in report
