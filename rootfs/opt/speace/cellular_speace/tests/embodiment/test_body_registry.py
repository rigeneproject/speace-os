import json
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.embodiment.body_registry import BodyRegistry


@pytest.fixture
def registry():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield BodyRegistry(storage_path=str(Path(tmpdir) / "body_registry.jsonl"))


class TestRegisterBody:
    def test_register_and_get(self, registry):
        registry.register_body(
            body_id="host_01",
            body_type="host",
            connection_string="local",
            capabilities={"sensors": ["cpu_sensor"], "actuators": ["file_writer"]},
        )
        body = registry.get_body("host_01")
        assert body is not None
        assert body["body_type"] == "host"
        assert body["connection_string"] == "local"
        assert body["health_score"] == 1.0
        assert "last_active" in body

    def test_register_overwrites(self, registry):
        registry.register_body(
            body_id="host_01",
            body_type="host",
            connection_string="local",
            capabilities={},
        )
        registry.register_body(
            body_id="host_01",
            body_type="robot",
            connection_string="tcp://192.168.1.5",
            capabilities={},
        )
        body = registry.get_body("host_01")
        assert body["body_type"] == "robot"

    def test_persistence(self, registry):
        registry.register_body(
            body_id="edge_01",
            body_type="edge",
            connection_string="mqtt://edge1.local",
            capabilities={"sensors": ["temperature_sensor"], "actuators": ["motor"]},
        )
        assert registry._storage_path.exists()
        lines = registry._storage_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["body_id"] == "edge_01"
        assert record["body_type"] == "edge"

    def test_load_existing(self, registry):
        registry.register_body(
            body_id="iot_01",
            body_type="iot",
            connection_string="http://iot1.local",
            capabilities={},
        )
        # Re-instantiate with same path
        registry2 = BodyRegistry(storage_path=str(registry._storage_path))
        body = registry2.get_body("iot_01")
        assert body is not None
        assert body["body_type"] == "iot"


class TestUnregisterBody:
    def test_unregister_existing(self, registry):
        registry.register_body("b1", "host", "local", {})
        assert registry.unregister_body("b1") is True
        assert registry.get_body("b1") is None

    def test_unregister_nonexistent(self, registry):
        assert registry.unregister_body("missing") is False

    def test_persistence_after_unregister(self, registry):
        registry.register_body("b1", "host", "local", {})
        registry.register_body("b2", "iot", "http://x", {})
        registry.unregister_body("b1")
        lines = registry._storage_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["body_id"] == "b2"


class TestGetBodiesByType:
    def test_filter_by_type(self, registry):
        registry.register_body("r1", "robot", "tcp://r1", {})
        registry.register_body("r2", "robot", "tcp://r2", {})
        registry.register_body("h1", "host", "local", {})
        robots = registry.get_bodies_by_type("robot")
        assert len(robots) == 2
        hosts = registry.get_bodies_by_type("host")
        assert len(hosts) == 1

    def test_empty_type(self, registry):
        assert registry.get_bodies_by_type("cloud_clone") == []


class TestGetBestBodyForTask:
    def test_selects_matching_body(self, registry):
        registry.register_body(
            "host_01",
            "host",
            "local",
            {"sensors": ["cpu_sensor"], "actuators": ["file_writer"]},
        )
        registry.register_body(
            "robot_01",
            "robot",
            "tcp://r1",
            {"sensors": ["camera", "motion_sensor"], "actuators": ["motor", "speaker"]},
        )
        best = registry.get_best_body_for_task(
            required_sensors=["camera"],
            required_actuators=["motor"],
        )
        assert best is not None
        assert best["body_id"] == "robot_01"

    def test_prefers_higher_health(self, registry):
        registry.register_body(
            "r1",
            "robot",
            "tcp://r1",
            {"sensors": ["camera"], "actuators": ["motor"]},
        )
        registry.register_body(
            "r2",
            "robot",
            "tcp://r2",
            {"sensors": ["camera"], "actuators": ["motor"]},
        )
        registry.update_health("r1", 0.3)
        registry.update_health("r2", 0.9)
        best = registry.get_best_body_for_task(
            required_sensors=["camera"],
            required_actuators=["motor"],
        )
        assert best["body_id"] == "r2"

    def test_returns_none_when_no_match(self, registry):
        registry.register_body(
            "r1",
            "robot",
            "tcp://r1",
            {"sensors": ["camera"], "actuators": ["motor"]},
        )
        best = registry.get_best_body_for_task(
            required_sensors=["temperature_sensor"],
            required_actuators=["motor"],
        )
        assert best is None

    def test_empty_requirements_match_any(self, registry):
        registry.register_body("h1", "host", "local", {})
        registry.register_body("h2", "host", "local", {})
        registry.update_health("h1", 0.2)
        registry.update_health("h2", 0.8)
        best = registry.get_best_body_for_task(required_sensors=[], required_actuators=[])
        assert best["body_id"] == "h2"


class TestUpdateHealth:
    def test_update_health(self, registry):
        registry.register_body("b1", "host", "local", {})
        assert registry.update_health("b1", 0.75) is True
        body = registry.get_body("b1")
        assert body["health_score"] == pytest.approx(0.75)

    def test_update_health_clamps(self, registry):
        registry.register_body("b1", "host", "local", {})
        registry.update_health("b1", 1.5)
        assert registry.get_body("b1")["health_score"] == pytest.approx(1.0)
        registry.update_health("b1", -0.3)
        assert registry.get_body("b1")["health_score"] == pytest.approx(0.0)

    def test_update_missing_body(self, registry):
        assert registry.update_health("missing", 0.5) is False

    def test_update_refreshes_last_active(self, registry):
        registry.register_body("b1", "host", "local", {})
        old_active = registry.get_body("b1")["last_active"]
        import time
        time.sleep(0.01)
        registry.update_health("b1", 0.9)
        new_active = registry.get_body("b1")["last_active"]
        assert new_active != old_active


class TestListAll:
    def test_list_all(self, registry):
        assert registry.list_all() == []
        registry.register_body("b1", "host", "local", {})
        registry.register_body("b2", "iot", "http://x", {})
        assert len(registry.list_all()) == 2
