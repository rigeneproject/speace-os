import pytest

from speace_core.cellular_brain.embodiment.cross_body_sensorimotor_coordinator import (
    CrossBodySensorimotorCoordinator,
)


class FakeSensorArray:
    def __init__(self, readings=None):
        self.readings = readings or {"cpu": 10.0}

    def read(self):
        return self.readings


class FakeEnvironmentModel:
    def __init__(self):
        self.state = {}

    def update(self, snapshot):
        self.state.update(snapshot)

    def predict_next_state(self):
        return {"predicted_cpu": self.state.get("cpu", 0.0) + 1.0}


class FakeActuator:
    def __init__(self):
        self.last_action = None

    def act(self, prediction):
        self.last_action = prediction
        return {"executed": True, "prediction": prediction}


@pytest.fixture
def coordinator():
    return CrossBodySensorimotorCoordinator()


@pytest.fixture
def fake_loop():
    return FakeSensorArray(), FakeEnvironmentModel(), FakeActuator()


class TestRegisterBodyLoop:
    def test_register_and_unregister(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        assert "host_01" in coordinator._loops
        assert coordinator.unregister_body_loop("host_01") is True
        assert "host_01" not in coordinator._loops

    def test_unregister_missing(self, coordinator):
        assert coordinator.unregister_body_loop("missing") is False


class TestStepBody:
    def test_step_success(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        result = coordinator.step_body("host_01", dt=0.5)
        assert result["status"] == "ok"
        assert result["body_id"] == "host_01"
        assert result["sensor_snapshot"] == {"cpu": 10.0}
        assert result["predicted_state"] == {"predicted_cpu": 11.0}
        assert result["action_outcome"]["executed"] is True

    def test_step_missing_body(self, coordinator):
        result = coordinator.step_body("missing")
        assert result["status"] == "error"
        assert "not registered" in result["error"]

    def test_step_history_limit(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        loop = coordinator._loops["host_01"]
        loop.history_limit = 5
        for _ in range(10):
            coordinator.step_body("host_01")
        assert len(loop.history) == 5


class TestStepAll:
    def test_step_all(self, coordinator, fake_loop):
        sensor1, model1, actuator1 = fake_loop
        sensor2, model2, actuator2 = FakeSensorArray({"cpu": 20.0}), FakeEnvironmentModel(), FakeActuator()
        coordinator.register_body_loop("host_01", sensor1, model1, actuator1)
        coordinator.register_body_loop("host_02", sensor2, model2, actuator2)
        results = coordinator.step_all(dt=1.0)
        assert len(results) == 2
        assert results["host_01"]["status"] == "ok"
        assert results["host_02"]["status"] == "ok"


class TestGetGlobalSensorimotorState:
    def test_empty_coordinator(self, coordinator):
        state = coordinator.get_global_sensorimotor_state()
        assert state["body_count"] == 0
        assert state["active_bodies"] == 0
        assert state["global_action_success_rate"] == 0.0

    def test_single_body(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        coordinator.step_body("host_01")
        state = coordinator.get_global_sensorimotor_state()
        assert state["body_count"] == 1
        assert state["active_bodies"] == 1
        assert state["global_action_success_rate"] == 1.0
        assert "cpu" in state["global_sensor_average"]

    def test_multiple_bodies(self, coordinator, fake_loop):
        sensor1, model1, actuator1 = fake_loop
        sensor2, model2, actuator2 = FakeSensorArray({"cpu": 30.0}), FakeEnvironmentModel(), FakeActuator()
        coordinator.register_body_loop("host_01", sensor1, model1, actuator1)
        coordinator.register_body_loop("host_02", sensor2, model2, actuator2)
        coordinator.step_all()
        state = coordinator.get_global_sensorimotor_state()
        assert state["body_count"] == 2
        assert state["global_sensor_average"]["cpu"] == pytest.approx(20.0)

    def test_body_summaries(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        coordinator.step_body("host_01")
        state = coordinator.get_global_sensorimotor_state()
        assert "host_01" in state["body_summaries"]
        assert state["body_summaries"]["host_01"]["tick_count"] == 1


class TestDetectBodyStress:
    def test_insufficient_history(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        result = coordinator.detect_body_stress("host_01")
        assert result["status"] == "error"
        assert "No history available" in result["error"]

    def test_no_stress(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        for _ in range(20):
            coordinator.step_body("host_01")
        result = coordinator.detect_body_stress("host_01")
        assert result["status"] == "ok"
        assert result["stress_detected"] is False
        assert result["anomaly_score"] == pytest.approx(0.0, abs=0.5)

    def test_stress_detected(self, coordinator, fake_loop):
        sensor, model, actuator = fake_loop
        coordinator.register_body_loop("host_01", sensor, model, actuator)
        # Build baseline with low cpu
        sensor.readings = {"cpu": 10.0}
        for _ in range(20):
            coordinator.step_body("host_01")
        # Spike cpu
        sensor.readings = {"cpu": 100.0}
        for _ in range(5):
            coordinator.step_body("host_01")
        result = coordinator.detect_body_stress("host_01")
        assert result["status"] == "ok"
        assert result["stress_detected"] is True
        assert result["anomaly_score"] > 2.0

    def test_missing_body(self, coordinator):
        result = coordinator.detect_body_stress("missing")
        assert result["status"] == "error"


class TestFlatten:
    def test_flatten_nested(self, coordinator):
        nested = {"a": {"b": 1.0, "c": 2.0}, "d": 3.0}
        flat = coordinator._flatten(nested)
        assert flat["a.b"] == 1.0
        assert flat["a.c"] == 2.0
        assert flat["d"] == 3.0

    def test_flatten_empty(self, coordinator):
        assert coordinator._flatten({}) == {}
