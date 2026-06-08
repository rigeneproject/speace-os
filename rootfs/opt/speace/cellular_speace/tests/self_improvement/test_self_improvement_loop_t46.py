import pytest
import tempfile

from speace_core.cellular_brain.self_improvement.outcome_tracker import ProposalOutcome
from speace_core.cellular_brain.self_improvement.self_improvement_loop import SelfImprovementLoop


class FakeMorphologicalMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class TestSelfImprovementLoopT46:
    def test_self_improvement_loop_records_proposal_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            loop = SelfImprovementLoop(memory=mem)
            outcome = loop.record_proposal_outcome(
                proposal_id="prop-001",
                limitation_type="semantic_association_missing",
                task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                metrics={"net_gain": 0.2903},
            )
            assert isinstance(outcome, ProposalOutcome)
            assert outcome.success is True

    def test_self_improvement_loop_learns_from_validated_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            loop = SelfImprovementLoop(memory=mem)
            outcome = loop.record_proposal_outcome(
                proposal_id="prop-001",
                limitation_type="semantic_association_missing",
                task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                metrics={"net_gain": 0.2903},
            )
            record = loop.learn_from_outcome(outcome)
            assert record.limitation_type == "semantic_association_missing"
            assert record.proposed_task_id == "T44"
            assert record.confidence > 0.0

    def test_self_improvement_loop_uses_learned_mapping_for_repeated_limitation(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            loop = SelfImprovementLoop(memory=mem)
            outcome = loop.record_proposal_outcome(
                proposal_id="prop-001",
                limitation_type="semantic_association_missing",
                task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                metrics={"net_gain": 0.2903},
            )
            loop.learn_from_outcome(outcome)
            candidates = [
                {"task_id": "T44", "proposal_id": "prop-001", "title": "T44"},
                {"task_id": "T45", "proposal_id": "prop-002", "title": "T45"},
            ]
            best = loop.get_best_known_proposal_for_limitation(
                "semantic_association_missing",
                candidates=candidates,
            )
            assert best is not None
            assert best["task_id"] == "T44"

    def test_get_best_known_proposal_returns_none_when_empty(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            loop = SelfImprovementLoop(memory=mem)
            best = loop.get_best_known_proposal_for_limitation(
                "unknown_limitation",
                candidates=[],
            )
            assert best is None

    def test_morphological_events_logged_for_success(self):
        mem = FakeMorphologicalMemory()
        loop = SelfImprovementLoop(memory=mem)
        outcome = loop.record_proposal_outcome(
            proposal_id="prop-001",
            limitation_type="semantic_association_missing",
            task_id="T44",
            audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
            metrics={"net_gain": 0.2903},
        )
        types = [str(e.event_type) for e in mem.events]
        assert any("SELF_IMPROVEMENT_OUTCOME_RECORDED" in t for t in types)
        assert any("SELF_IMPROVEMENT_PROPOSAL_VALIDATED" in t for t in types)

    def test_morphological_events_logged_for_failure(self):
        mem = FakeMorphologicalMemory()
        loop = SelfImprovementLoop(memory=mem)
        outcome = loop.record_proposal_outcome(
            proposal_id="prop-002",
            limitation_type="semantic_association_missing",
            task_id="T44",
            audit_verdict="ENERGY_REGRESSION",
            metrics={"net_gain": -0.1},
        )
        types = [str(e.event_type) for e in mem.events]
        assert any("SELF_IMPROVEMENT_OUTCOME_RECORDED" in t for t in types)
        assert any("SELF_IMPROVEMENT_PROPOSAL_FAILED" in t for t in types)

    def test_benchmark_metrics_defaults(self):
        from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
        m = BenchmarkMetrics()
        assert m.self_improvement_outcome_count == 0
        assert m.self_improvement_success_rate == 0.0
        assert m.self_improvement_regression_rate == 0.0
        assert m.self_improvement_mean_net_gain == 0.0
        assert m.self_improvement_learning_confidence == 0.0
        assert m.validated_proposal_count == 0
        assert m.failed_proposal_count == 0

    def test_self_improvement_memory_records_via_loop(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            loop = SelfImprovementLoop(memory=mem)
            outcome = loop.record_proposal_outcome(
                proposal_id="prop-001",
                limitation_type="semantic_association_missing",
                task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                metrics={"net_gain": 0.2903},
            )
            loop.learn_from_outcome(outcome)
            summary = loop.self_improvement_memory.summarize()
            assert summary["outcome_count"] >= 1
            assert summary["learning_update_count"] >= 1
