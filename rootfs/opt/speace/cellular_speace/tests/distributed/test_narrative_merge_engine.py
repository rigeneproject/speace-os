import pytest

from speace_core.cellular_brain.distributed.narrative_merge_engine import (
    NarrativeMergeEngine,
)


class TestNarrativeMergeEngine:
    def test_add_and_get_merged_narrative(self):
        engine = NarrativeMergeEngine()
        engine.add_narrative("node-a", {"timestamp": "2024-01-01T00:00:02Z", "event": "boot"})
        engine.add_narrative("node-b", {"timestamp": "2024-01-01T00:00:01Z", "event": "boot"})
        merged = engine.get_merged_narrative()
        assert len(merged) == 2
        # Should be chronological
        assert merged[0]["node_id"] == "node-b"
        assert merged[1]["node_id"] == "node-a"

    def test_detect_conflicts(self):
        engine = NarrativeMergeEngine()
        engine.add_narrative(
            "node-a",
            {"tick": 1, "event_type": "state_change", "data": "X", "checksum": "c1"},
        )
        engine.add_narrative(
            "node-b",
            {"tick": 1, "event_type": "state_change", "data": "Y", "checksum": "c2"},
        )
        conflicts = engine.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]["reason"] == "divergent_payload"
        assert len(conflicts[0]["events"]) == 2

    def test_resolve_conflict_keeps_higher_trust(self):
        engine = NarrativeMergeEngine(node_trust={"node-a": 0.9, "node-b": 0.4})
        ev_a = {"node_id": "node-a", "tick": 1, "data": "X"}
        ev_b = {"node_id": "node-b", "tick": 1, "data": "Y"}
        resolution = engine.resolve_conflict(ev_a, ev_b)
        assert resolution["winner"]["node_id"] == "node-a"
        assert resolution["loser"]["node_id"] == "node-b"
        assert resolution["reason"] == "higher_trust"
        assert resolution["flag_for_review"] is True
