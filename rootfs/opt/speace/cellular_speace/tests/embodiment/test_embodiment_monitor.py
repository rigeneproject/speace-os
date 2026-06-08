import pytest

from speace_core.cellular_brain.embodiment.embodiment_monitor import EmbodimentMonitor


class TestEmbodimentMonitor:
    def test_initialization(self):
        monitor = EmbodimentMonitor(window_size=50)
        assert monitor.window_size == 50
        assert monitor._tick_count == 0

    def test_evaluate_tick_no_action(self):
        monitor = EmbodimentMonitor(window_size=10)
        sensor_before = {"cpu": {"usage_percent": 10.0}}
        sensor_after = {"cpu": {"usage_percent": 10.0}}
        result = monitor.evaluate_tick(
            sensor_before=sensor_before,
            action=None,
            sensor_after=sensor_after,
            prediction=None,
        )
        assert result["loop_closure_latency_ms"] == 0.0
        assert result["prediction_accuracy"] == 0.0
        assert result["action_success"] is False
        assert result["sensorimotor_coherence"] == 0.0
        assert result["embodiment_depth"] == pytest.approx(0.2)

    def test_evaluate_tick_with_action_and_prediction(self):
        monitor = EmbodimentMonitor(window_size=10)
        sensor_before = {"cpu": {"usage_percent": 10.0}}
        sensor_after = {"cpu": {"usage_percent": 15.0}}
        prediction = {"cpu.usage_percent": 15.0}
        action = {"action_id": "test_action"}
        result = monitor.evaluate_tick(
            sensor_before=sensor_before,
            action=action,
            sensor_after=sensor_after,
            prediction=prediction,
        )
        assert result["embodiment_depth"] == pytest.approx(1.0)
        assert result["action_success"] is True
        assert result["prediction_accuracy"] == pytest.approx(1.0)
        assert result["sensorimotor_coherence"] == pytest.approx(0.0)

    def test_evaluate_tick_prediction_accuracy_partial(self):
        monitor = EmbodimentMonitor(window_size=10)
        sensor_before = {"cpu": {"usage_percent": 10.0}}
        sensor_after = {"cpu": {"usage_percent": 12.0}}
        prediction = {"cpu.usage_percent": 14.0}
        result = monitor.evaluate_tick(
            sensor_before=sensor_before,
            action=None,
            sensor_after=sensor_after,
            prediction=prediction,
        )
        rel_error = abs(12.0 - 14.0) / max(12.0, 14.0, 1.0)
        expected_accuracy = 1.0 - rel_error
        assert result["prediction_accuracy"] == pytest.approx(expected_accuracy)

    def test_embodiment_report_empty(self):
        monitor = EmbodimentMonitor()
        report = monitor.get_embodiment_report()
        assert report["loop_closure_latency_ms"] == 0.0
        assert report["prediction_accuracy"] == 0.0
        assert report["action_success_rate"] == 0.0
        assert report["sensorimotor_coherence"] == 0.0
        assert report["embodiment_depth"] == 0.0
        assert report["tick_count"] == 0

    def test_embodiment_report_after_ticks(self):
        monitor = EmbodimentMonitor(window_size=10)
        for i in range(5):
            sensor_before = {"cpu": {"usage_percent": float(i)}}
            sensor_after = {"cpu": {"usage_percent": float(i + 1)}}
            monitor.evaluate_tick(
                sensor_before=sensor_before,
                action={"id": f"act_{i}"},
                sensor_after=sensor_after,
                prediction=None,
            )
        report = monitor.get_embodiment_report()
        assert report["tick_count"] == 5
        assert report["action_success_rate"] == pytest.approx(1.0)
        assert report["embodiment_depth"] == pytest.approx(0.6)

    def test_coherence_calculation(self):
        monitor = EmbodimentMonitor(window_size=10)
        sensor_before = {"cpu": {"usage_percent": 10.0}, "mem": {"percent": 50.0}}
        sensor_after = {"cpu": {"usage_percent": 12.0}, "mem": {"percent": 55.0}}
        prediction = {"cpu.usage_percent": 12.0, "mem.percent": 55.0}
        result = monitor.evaluate_tick(
            sensor_before=sensor_before,
            action={"id": "act1"},
            sensor_after=sensor_after,
            prediction=prediction,
        )
        assert result["sensorimotor_coherence"] == pytest.approx(1.0)

    def test_flatten_snapshot(self):
        snapshot = {
            "cpu": {"usage_percent": 10.0, "frequency_mhz": 2000},
            "memory": {"used_bytes": 1000},
            "scalar": 42.0,
        }
        flat = EmbodimentMonitor._flatten_snapshot(snapshot)
        assert flat["cpu.usage_percent"] == 10.0
        assert flat["cpu.frequency_mhz"] == 2000.0
        assert flat["memory.used_bytes"] == 1000.0
        assert flat["scalar"] == 42.0
