"""Tests for DistributedOrganismController — Phase 4 Distributed Mature Organism."""

import json
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.embodiment.distributed_organism_controller import (
    DistributedOrganismController,
)


@pytest.fixture
def controller():
    with tempfile.TemporaryDirectory() as tmpdir:
        from speace_core.cellular_brain.embodiment.body_registry import BodyRegistry
        registry = BodyRegistry(storage_path=str(Path(tmpdir) / "body_registry.jsonl"))
        c = DistributedOrganismController(data_root=tmpdir, body_registry=registry)
        yield c


class TestDistributedOrganismController:
    def test_register_and_list_nodes(self, controller):
        controller.register_node(
            node_id="node_a",
            node_type="edge",
            capabilities={"sensors": ["camera"], "actuators": ["servo"]},
        )
        nodes = controller.list_nodes()
        assert len(nodes) == 1
        assert nodes[0]["body_id"] == "node_a"
        assert nodes[0]["body_type"] == "edge"

    def test_unregister_node(self, controller):
        controller.register_node("node_b", "cloud", {})
        assert controller.unregister_node("node_b") is True
        assert controller.list_nodes() == []
        assert controller.unregister_node("node_b") is False

    def test_observe_distributed_state(self, controller):
        controller.register_node("n1", "edge", {"sensors": ["cam"], "actuators": ["light"]})
        controller.register_node("n2", "cloud", {"sensors": ["mic"], "actuators": []})
        state = controller.observe_distributed_state()
        assert state["node_count"] == 2
        assert "camera" not in state["sensor_inventory"]  # key is "cam"
        assert state["sensor_inventory"]["cam"] == 1
        assert state["actuator_inventory"]["light"] == 1
        assert "average_health" in state

    def test_propose_distributed_action_blocked(self, controller):
        pid = controller.propose_distributed_action(
            {"action_type": "coordinated_move", "nodes": ["n1"], "params": {}}
        )
        assert pid.startswith("dist_")
        proposal = controller._proposals[pid]
        assert proposal["status"] == "blocked"

    def test_evaluate_consensus(self, controller):
        controller.register_node("n1", "edge", {})
        controller.register_node("n2", "edge", {})
        controller.register_node("n3", "edge", {})
        pid = controller.propose_distributed_action({"action_type": "coordinated_speak"})
        consensus = controller.evaluate_consensus(pid)
        assert consensus["total_nodes"] == 3
        # required = max(1, int(0.66 * 3)) = max(1, 1) = 1
        assert consensus["required_votes"] == 1
        # Simulated votes always fall short for safety (approve = required - 1)
        assert consensus["quorum_reached"] is False
        assert consensus["status"] == "quorum_failed"

    def test_summary(self, controller):
        controller.register_node("n1", "edge", {}, health_score=0.9)
        controller.register_node("n2", "edge", {}, health_score=0.7)
        controller.propose_distributed_action({"action_type": "test"})
        summary = controller.summary()
        assert summary["node_count"] == 2
        assert summary["average_health"] == 0.8
        assert summary["total_proposals"] == 1
        assert summary["blocked_proposals"] == 1
        assert summary["autonomous_execution_enabled"] is False

    def test_history(self, controller):
        controller.register_node("n1", "edge", {})
        controller.propose_distributed_action({"action_type": "test"})
        hist = controller.get_action_history()
        assert len(hist) == 1
        assert hist[0]["outcome"] == "blocked"

    def test_audit_log_written(self, controller):
        controller.register_node("n_audit", "cloud", {})
        audit_path = Path(controller._data_root) / "distributed_organism_audit.jsonl"
        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert "timestamp" in record
        assert "action_id" in record

    def test_persist_proposals(self, controller):
        controller.propose_distributed_action({"action_type": "persist_test"})
        proposals_path = Path(controller._data_root) / "distributed_proposals.jsonl"
        assert proposals_path.exists()
        lines = proposals_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert record["action_type"] == "persist_test"
        assert record["status"] == "blocked"
