import pytest
import tempfile
from pathlib import Path

from speace_core.cellular_brain.self_improvement.outcome_tracker import (
    OutcomeTracker,
    ProposalOutcome,
)


class FakeMorphologicalMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class TestOutcomeTracker:
    def test_record_successful_outcome_from_validated_verdict(self):
        mem = FakeMorphologicalMemory()
        tracker = OutcomeTracker(memory=mem)
        outcome = tracker.record_outcome(
            proposal_id="prop-001",
            limitation_type="semantic_association_missing",
            task_id="T44",
            audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
            metrics={"net_gain": 0.29, "cognitive_delta": 0.1, "phi_delta": 0.05},
        )
        assert outcome.success is True
        assert outcome.partial_success is False
        assert outcome.regression_detected is False
        assert outcome.net_gain == pytest.approx(0.29)

    def test_record_partial_success_from_positive_small_net_gain(self):
        mem = FakeMorphologicalMemory()
        tracker = OutcomeTracker(memory=mem)
        outcome = tracker.record_outcome(
            proposal_id="prop-002",
            limitation_type="semantic_association_missing",
            task_id="T44",
            audit_verdict="ASSOCIATIVE_RECALL_WEAK",
            metrics={"net_gain": 0.03},
        )
        assert outcome.success is False
        assert outcome.partial_success is True
        assert outcome.regression_detected is False

    def test_record_regression_from_negative_net_gain(self):
        mem = FakeMorphologicalMemory()
        tracker = OutcomeTracker(memory=mem)
        outcome = tracker.record_outcome(
            proposal_id="prop-003",
            limitation_type="semantic_association_missing",
            task_id="T44",
            audit_verdict="ENERGY_REGRESSION",
            metrics={"net_gain": -0.1},
        )
        assert outcome.success is False
        assert outcome.partial_success is False
        assert outcome.regression_detected is True

    def test_outcome_persistence_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = OutcomeTracker(base_path=td)
            outcome = tracker.record_outcome(
                proposal_id="prop-004",
                limitation_type="semantic_association_missing",
                task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                metrics={"net_gain": 0.2},
            )
            loaded = tracker.load_outcomes()
            assert len(loaded) >= 1
            ids = [o.id for o in loaded]
            assert outcome.id in ids

    def test_load_outcomes_for_limitation(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = OutcomeTracker(base_path=td)
            tracker.record_outcome(
                proposal_id="prop-a",
                limitation_type="semantic_association_missing",
                task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                metrics={"net_gain": 0.2},
            )
            tracker.record_outcome(
                proposal_id="prop-b",
                limitation_type="other_limitation",
                task_id="T47",
                audit_verdict="VALIDATED",
                metrics={"net_gain": 0.3},
            )
            results = tracker.get_outcomes_for_limitation("semantic_association_missing")
            assert len(results) >= 1
            assert all(o.originating_limitation_type == "semantic_association_missing" for o in results)

    def test_generate_outcome_report_contains_required_fields(self):
        tracker = OutcomeTracker()
        outcome = ProposalOutcome(
            id="out-001",
            proposal_id="prop-001",
            originating_limitation_type="semantic_association_missing",
            implemented_task_id="T44",
            audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
            net_gain=0.29,
            success=True,
            timestamp="2026-05-17T00:00:00",
        )
        report = tracker.generate_outcome_report(outcome)
        assert "T46" in report
        assert "out-001" in report
        assert "ASSOCIATIVE_MEMORY_VALIDATED" in report
        assert "0.2900" in report or "0.29" in report

    def test_verdict_validated_triggers_success_even_with_low_gain(self):
        tracker = OutcomeTracker()
        outcome = tracker.record_outcome(
            proposal_id="prop-x",
            limitation_type="x",
            task_id="Tx",
            audit_verdict="PARTIAL_VALIDATED",
            metrics={"net_gain": 0.01},
        )
        assert outcome.success is True

    def test_verdict_regression_triggers_regression_even_with_small_negative(self):
        tracker = OutcomeTracker()
        outcome = tracker.record_outcome(
            proposal_id="prop-y",
            limitation_type="y",
            task_id="Ty",
            audit_verdict="SOME_REGRESSION_DETECTED",
            metrics={"net_gain": -0.01},
        )
        assert outcome.regression_detected is True
