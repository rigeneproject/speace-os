import pytest
import tempfile
from pathlib import Path

from speace_core.cellular_brain.self_improvement.self_improvement_memory import (
    SelfImprovementMemory,
)


class TestSelfImprovementMemory:
    def test_writes_history_event(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            entry = mem.write_history_event("test_event", {"key": "value"})
            assert entry.entry_type == "test_event"
            assert entry.data["key"] == "value"

    def test_loads_history(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            mem.write_history_event("event_a", {"x": 1})
            mem.write_history_event("event_b", {"y": 2})
            history = mem.load_history()
            assert len(history) == 2
            types = [e.entry_type for e in history]
            assert "event_a" in types
            assert "event_b" in types

    def test_get_history_by_type(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            mem.write_history_event("audit_outcome", {"verdict": "OK"})
            mem.write_history_event("learning_update", {"confidence": 0.8})
            results = mem.get_history_by_type("audit_outcome")
            assert len(results) == 1
            assert results[0].data["verdict"] == "OK"

    def test_record_limitation_detected(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            entry = mem.record_limitation_detected("semantic_association_missing", {"severity": 0.8})
            assert entry.entry_type == "limitation_detected"
            assert entry.data["limitation_type"] == "semantic_association_missing"

    def test_record_proposal_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            entry = mem.record_proposal_accepted("prop-1", "semantic_association_missing")
            assert entry.entry_type == "proposal_accepted"

    def test_record_proposal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            entry = mem.record_proposal_rejected("prop-2", "semantic_association_missing", "unsafe")
            assert entry.entry_type == "proposal_rejected"
            assert entry.data["reason"] == "unsafe"

    def test_record_audit_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            entry = mem.record_audit_outcome("out-1", "prop-1", "VALIDATED", 0.29)
            assert entry.entry_type == "audit_outcome"
            assert entry.data["net_gain"] == pytest.approx(0.29)

    def test_record_learning_update(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            entry = mem.record_learning_update("l1", "T44", 0.85, 0.29)
            assert entry.entry_type == "learning_update"
            assert entry.data["confidence"] == pytest.approx(0.85)

    def test_summarize_counts(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            mem.record_limitation_detected("l1", {})
            mem.record_proposal_generated("p1", "l1", "T44")
            mem.record_proposal_accepted("p1", "l1")
            mem.record_audit_outcome("o1", "p1", "VALIDATED", 0.2)
            summary = mem.summarize()
            assert summary["limitation_count"] == 1
            assert summary["proposal_count"] == 1
            assert summary["accepted_count"] == 1
            assert summary["outcome_count"] == 1

    def test_duplicate_outcome_does_not_corrupt_learning(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SelfImprovementMemory(base_path=td)
            for i in range(3):
                mem.record_audit_outcome(f"o{i}", "p1", "VALIDATED", 0.2)
            history = mem.load_history()
            assert len(history) == 3
