import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.embodiment.body_registry import BodyRegistry
from speace_core.cellular_brain.embodiment.body_router import BodyRouter


@pytest.fixture
def router():
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = BodyRegistry(storage_path=str(Path(tmpdir) / "registry.jsonl"))
        yield BodyRouter(registry=registry)


class TestRouteSensorCommand:
    def test_sensor_command_success(self, router):
        router._registry.register_body(
            "edge_01",
            "edge",
            "mqtt://edge1",
            {"sensors": ["temperature_sensor", "light_sensor"], "actuators": []},
        )
        result = router.route_sensor_command("edge_01", "temperature_sensor")
        assert result["status"] == "ok"
        assert result["body_id"] == "edge_01"
        assert result["sensor_type"] == "temperature_sensor"
        assert "reading" in result

    def test_sensor_command_missing_body(self, router):
        result = router.route_sensor_command("missing", "temperature_sensor")
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_sensor_command_missing_sensor(self, router):
        router._registry.register_body(
            "edge_01",
            "edge",
            "mqtt://edge1",
            {"sensors": ["light_sensor"], "actuators": []},
        )
        result = router.route_sensor_command("edge_01", "temperature_sensor")
        assert result["status"] == "error"
        assert "not available" in result["error"]


class TestRouteActionCommand:
    def test_action_command_success(self, router):
        router._registry.register_body(
            "robot_01",
            "robot",
            "tcp://r1",
            {"sensors": [], "actuators": ["motor", "speaker"]},
        )
        result = router.route_action_command("robot_01", "motor", {"speed": 0.5})
        assert result["status"] == "ok"
        assert result["body_id"] == "robot_01"
        assert result["action_type"] == "motor"
        assert result["result"]["params"] == {"speed": 0.5}

    def test_action_command_missing_body(self, router):
        result = router.route_action_command("missing", "motor")
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_action_command_missing_actuator(self, router):
        router._registry.register_body(
            "robot_01",
            "robot",
            "tcp://r1",
            {"sensors": [], "actuators": ["motor"]},
        )
        result = router.route_action_command("robot_01", "speaker")
        assert result["status"] == "error"
        assert "not available" in result["error"]

    def test_action_command_no_params(self, router):
        router._registry.register_body(
            "robot_01",
            "robot",
            "tcp://r1",
            {"sensors": [], "actuators": ["motor"]},
        )
        result = router.route_action_command("robot_01", "motor")
        assert result["status"] == "ok"
        assert result["result"]["params"] == {}


class TestBroadcastToAll:
    def test_broadcast_no_bodies(self, router):
        result = router.broadcast_to_all("temperature_sensor")
        assert result["status"] == "ok"
        assert result["bodies_queried"] == 0
        assert result["aggregate"] == 0.0

    def test_broadcast_multiple_bodies(self, router):
        router._registry.register_body(
            "edge_01",
            "edge",
            "mqtt://e1",
            {"sensors": ["temperature_sensor"], "actuators": []},
        )
        router._registry.register_body(
            "edge_02",
            "edge",
            "mqtt://e2",
            {"sensors": ["temperature_sensor"], "actuators": []},
        )
        result = router.broadcast_to_all("temperature_sensor")
        assert result["bodies_queried"] == 2
        assert result["successful"] == 2
        assert "readings" in result
        assert len(result["readings"]) == 2

    def test_broadcast_partial_failure(self, router):
        router._registry.register_body(
            "edge_01",
            "edge",
            "mqtt://e1",
            {"sensors": ["temperature_sensor"], "actuators": []},
        )
        router._registry.register_body(
            "edge_02",
            "edge",
            "mqtt://e2",
            {"sensors": ["light_sensor"], "actuators": []},
        )
        result = router.broadcast_to_all("temperature_sensor")
        assert result["bodies_queried"] == 2
        assert result["successful"] == 1


class TestSelectBodyForTask:
    def test_select_by_keywords(self, router):
        router._registry.register_body(
            "robot_01",
            "robot",
            "tcp://r1",
            {"sensors": ["camera", "motion_sensor"], "actuators": ["motor"]},
        )
        router._registry.register_body(
            "host_01",
            "host",
            "local",
            {"sensors": ["cpu_sensor"], "actuators": ["file_writer"]},
        )
        selected = router.select_body_for_task("Move the robot with camera")
        assert selected is not None
        assert selected["body_id"] == "robot_01"

    def test_select_no_match(self, router):
        router._registry.register_body(
            "host_01",
            "host",
            "local",
            {"sensors": ["cpu_sensor"], "actuators": ["file_writer"]},
        )
        selected = router.select_body_for_task("Launch rocket")
        assert selected is None

    def test_select_prefers_healthier(self, router):
        router._registry.register_body(
            "r1",
            "robot",
            "tcp://r1",
            {"sensors": ["camera"], "actuators": ["motor"]},
        )
        router._registry.register_body(
            "r2",
            "robot",
            "tcp://r2",
            {"sensors": ["camera"], "actuators": ["motor"]},
        )
        router._registry.update_health("r1", 0.2)
        router._registry.update_health("r2", 0.9)
        selected = router.select_body_for_task("Move with camera")
        assert selected["body_id"] == "r2"
